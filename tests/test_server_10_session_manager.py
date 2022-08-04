import pytest
from cryptojwt.jws.jws import factory

from idpyoidc.message.oidc import AuthorizationRequest
from idpyoidc.server import Server
from idpyoidc.server.authn_event import AuthnEvent
from idpyoidc.server.authn_event import create_authn_event
from idpyoidc.server.authz import AuthzHandling
from idpyoidc.server.session import MintingNotAllowed
from idpyoidc.server.session.info import ClientSessionInfo
from idpyoidc.server.session.token import AccessToken
from idpyoidc.server.session.token import AuthorizationCode
from idpyoidc.server.session.token import RefreshToken
from idpyoidc.time_util import utc_time_sans_frac

from . import CRYPT_CONFIG
from . import SESSION_PARAMS
from . import full_path

AUTH_REQ = AuthorizationRequest(
    client_id="client_1",
    redirect_uri="https://example.com/cb",
    scope=["openid"],
    state="STATE",
    response_type="code",
)

KEYDEFS = [
    {"type": "RSA", "key": "", "use": ["sig"]},
    {"type": "EC", "crv": "P-256", "use": ["sig"]},
]

USER_ID = "diana"

CLI1 = "https://client1.example.com/"


class TestSessionManager:
    @pytest.fixture(autouse=True)
    def create_session_manager(self):
        conf = {
            "issuer": "https://example.com/",
            "httpc_params": {"verify": False, "timeout": 1},
            "keys": {"key_defs": KEYDEFS, "uri_path": "static/jwks.json"},
            "jwks_uri": "https://example.com/jwks.json",
            "token_handler_args": {
                "jwks_def": {
                    "private_path": "private/token_jwks.json",
                    "read_only": False,
                    "key_defs": [{"type": "oct", "bytes": "24", "use": ["enc"], "kid": "code"}],
                },
                "code": {"lifetime": 600, "kwargs": {"crypt_conf": CRYPT_CONFIG}},
                "token": {
                    "class": "idpyoidc.server.token.jwt_token.JWTToken",
                    "kwargs": {
                        "lifetime": 3600,
                        "add_claims": True,
                        "add_claims_by_scope": True,
                        "aud": ["https://example.org/appl"],
                    },
                },
                "refresh": {
                    "class": "idpyoidc.server.token.jwt_token.JWTToken",
                    "kwargs": {
                        "lifetime": 3600,
                        "aud": ["https://example.org/appl"],
                    },
                },
                "id_token": {
                    "class": "idpyoidc.server.token.id_token.IDToken",
                    "kwargs": {
                        "base_claims": {
                            "email": {"essential": True},
                            "email_verified": {"essential": True},
                        }
                    },
                },
            },
            "session_params": SESSION_PARAMS,
            "template_dir": "template",
            "claims_interface": {
                "class": "idpyoidc.server.session.claims.ClaimsInterface",
                "kwargs": {},
            },
            "userinfo": {
                "class": "idpyoidc.server.user_info.UserInfo",
                "kwargs": {"db_file": full_path("users.json")},
            },
        }
        server = Server(conf)
        self.server = server
        self.endpoint_context = server.endpoint_context
        self.endpoint_context.cdb = {
            "client_1": {
                "client_secret": "hemligt",
                "redirect_uris": [("{}cb".format(CLI1), None)],
                "client_salt": "salted",
                "token_endpoint_auth_method": "client_secret_post",
                "response_types": ["code", "token", "code id_token", "id_token"],
                "post_logout_redirect_uri": (f"{CLI1}logout_cb", ""),
                "token_usage_rules": {
                    "authorization_code": {
                        "supports_minting": ["access_token", "refresh_token", "id_token"]
                    },
                    "refresh_token": {"supports_minting": ["id_token"]},
                },
            }
        }

        self.session_manager = server.endpoint_context.session_manager
        self.authn_event = AuthnEvent(
            uid="uid", valid_until=utc_time_sans_frac() + 1, authn_info="authn_class_ref"
        )
        self.dummy_branch_id = self.session_manager.encrypted_branch_id(
            "user_id", "client_id", "grant.id"
        )

    def _create_session(self, authorization_request, sub_type="public", sector_identifier=""):
        if sector_identifier:
            authz_req = authorization_request.copy()
            authz_req["sector_identifier_uri"] = sector_identifier
        else:
            authz_req = authorization_request

        client_id = authz_req["client_id"]
        ae = create_authn_event(USER_ID)
        return self.server.endpoint_context.session_manager.create_session(
            ae, authz_req, USER_ID, client_id=client_id, sub_type=sub_type, scope=["openid"]
        )

    @pytest.mark.parametrize(
        "sub_type, sector_identifier",
        [("pairwise", "https://all.example.com"), ("public", ""), ("ephemeral", "")],
    )
    def test_create_session_sub_type(self, sub_type, sector_identifier):
        # First session
        authz_req = AUTH_REQ.copy()
        if sub_type == "pairwise":
            authz_req["sector_identifier_uri"] = sector_identifier

        session_key_1 = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=authz_req,
            user_id="diana",
            client_id="client_1",
            sub_type=sub_type
        )

        _user_info_1 = self.session_manager.get_user_info(session_key_1)
        assert _user_info_1.subordinate == ['diana;;client_1']
        _client_info_1 = self.session_manager.get_client_session_info(session_key_1)
        assert len(_client_info_1.subordinate) == 1
        # grant = self.session_manager.get_grant(session_key_1)

        # Second session
        authn_req = AUTH_REQ.copy()
        authn_req["client_id"] = "client_2"
        if sub_type == "pairwise":
            authn_req["sector_identifier_uri"] = sector_identifier

        session_key_2 = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=authn_req,
            user_id="diana",
            client_id="client_2",
            sub_type=sub_type,
        )

        _user_info_2 = self.session_manager.get_user_info(session_key_2)
        assert _user_info_2.subordinate == ['diana;;client_1', "diana;;client_2"]

        grant_1 = self.session_manager.get_grant(session_key_1)
        grant_2 = self.session_manager.get_grant(session_key_2)

        if sub_type in ["pairwise", "public"]:
            assert grant_1.sub == grant_2.sub
        else:
            assert grant_1.sub != grant_2.sub

        # Third session
        authn_req = AUTH_REQ.copy()
        authn_req["client_id"] = "client_3"
        if sub_type == "pairwise":
            authn_req["sector_identifier_uri"] = sector_identifier

        session_key_3 = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=authn_req,
            user_id="diana",
            client_id="client_3",
            sub_type=sub_type,
        )

        grant_3 = self.session_manager.get_grant(session_key_3)

        if sub_type == "pairwise":
            assert grant_1.sub == grant_2.sub
            assert grant_1.sub == grant_3.sub
            assert grant_3.sub == grant_2.sub
        elif sub_type == "public":
            assert grant_1.sub == grant_2.sub
            assert grant_1.sub == grant_3.sub
            assert grant_3.sub == grant_2.sub
        else:
            assert grant_1.sub != grant_2.sub
            assert grant_1.sub != grant_3.sub
            assert grant_3.sub != grant_2.sub

        # Sub types differ so do authentication request

        assert grant_1.authorization_request != grant_2.authorization_request
        assert grant_1.authorization_request != grant_3.authorization_request
        assert grant_3.authorization_request != grant_2.authorization_request

    def _mint_token(self, branch_id, token_class, grant, based_on=None):
        # Constructing an authorization code is now done
        return grant.mint_token(
            branch_id,
            endpoint_context=self.endpoint_context,
            token_class=token_class,
            token_handler=self.session_manager.token_handler.handler[token_class],
            expires_at=utc_time_sans_frac() + 300,  # 5 minutes from now
            based_on=based_on,
            scope=["openid"]
        )

    def test_code_usage(self):
        branch_id = self._create_session(AUTH_REQ)
        branch_info = self.endpoint_context.session_manager.branch_info(branch_id, "grant")
        grant = branch_info["grant"]

        assert grant.issued_token == []
        assert grant.is_active() is True

        code = self._mint_token(branch_id, "authorization_code", grant)
        assert isinstance(code, AuthorizationCode)
        assert code.is_active()
        assert len(grant.issued_token) == 1

        assert code.usage_rules["supports_minting"] == [
            "access_token",
            "refresh_token",
            "id_token",
        ]
        access_token = self._mint_token(branch_id, "access_token", grant, code)
        assert isinstance(access_token, AccessToken)
        assert access_token.is_active()
        assert len(grant.issued_token) == 2

        refresh_token = self._mint_token(branch_id, "refresh_token", grant, code)
        assert isinstance(refresh_token, RefreshToken)
        assert refresh_token.is_active()
        assert len(grant.issued_token) == 3

        code.register_usage()
        assert code.max_usage_reached() is True

        with pytest.raises(MintingNotAllowed):
            self._mint_token(self.dummy_branch_id, "access_token", grant, code)

        grant.revoke_token(based_on=code.value)

        assert access_token.revoked is True
        assert refresh_token.revoked is True

    def test_check_grant(self):
        branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            scope=["openid", "phoe"],
        )

        _branch_info = self.session_manager.branch_info(branch_id, "grant")
        grant = _branch_info["grant"]
        assert grant.scope == ["openid", "phoe"]

        _grant = self.session_manager.get(["diana", "client_1", grant.id])

        assert _grant.scope == ["openid", "phoe"]

    def test_find_token(self):
        branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
        )

        _info = self.session_manager.branch_info(branch_id, "grant")
        grant = _info["grant"]

        code = self._mint_token(branch_id, "authorization_code", grant)
        access_token = self._mint_token(branch_id, "access_token", grant, code)

        _branch_id = self.session_manager.encrypted_branch_id("diana", "client_1", grant.id)
        _token = self.session_manager.find_token(_branch_id, access_token.value)

        assert _token.token_class == "access_token"
        assert _token.id == access_token.id

    def test_get_authentication_event(self):
        branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            # test taking the client_id from the authn request
            # client_id="client_1",
        )

        _info = self.session_manager.branch_info(branch_id, "grant")
        authn_event = _info["grant"].authentication_event

        assert isinstance(authn_event, AuthnEvent)
        assert authn_event["uid"] == "uid"
        assert authn_event["authn_info"] == "authn_class_ref"

        # cover the remaining one ...
        _info = self.session_manager.branch_info(branch_id, "grant")
        _ = _info["grant"].authorization_request

    def test_get_client_branch_info(self):
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
        )

        _info = self.session_manager.branch_info(_branch_id, "client")

        assert isinstance(_info["client"], ClientSessionInfo)

    def test_get_general_branch_info(self):
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
        )

        _branch_info = self.session_manager.branch_info(_branch_id)

        assert set(_branch_info.keys()) == {
            "branch_id",
            "client_id",
            "grant_id",
            "user_id",
            "user",
            "client",
            "grant"
        }
        assert _branch_info["user_id"] == "diana"
        assert _branch_info["client_id"] == "client_1"

    def test_get_branch_info_by_token(self):
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
        )

        grant = self.session_manager.get_grant(_branch_id)
        code = self._mint_token(_branch_id, "authorization_code", grant)
        _branch_info = self.session_manager.get_branch_info_by_token(code.value)

        assert set(_branch_info.keys()) == {
            "client_id",
            "grant_id",
            "user_id",
            "user",
            "client",
            "grant",
            "branch_id"
        }
        assert _branch_info["user_id"] == "diana"
        assert _branch_info["client_id"] == "client_1"

    def test_token_usage_default(self):
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
        )
        grant = self.session_manager[_branch_id]

        code = self._mint_token(_branch_id, "authorization_code", grant)

        assert code.usage_rules == {
            "max_usage": 1,
            "supports_minting": ["access_token", "refresh_token", "id_token"],
        }

        token = self._mint_token(_branch_id, "access_token", grant, code)

        assert token.usage_rules == {}

        refresh_token = self._mint_token(_branch_id, "refresh_token", grant, code)

        assert refresh_token.usage_rules == {"supports_minting": ["access_token", "refresh_token"]}

    def test_token_usage_grant(self):
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
        )
        grant = self.session_manager[_branch_id]
        grant.usage_rules = {
            "authorization_code": {
                "max_usage": 1,
                "supports_minting": ["access_token", "refresh_token", "id_token"],
                "expires_in": 300,
            },
            "access_token": {"expires_in": 3600},
            "refresh_token": {"supports_minting": ["access_token", "refresh_token", "id_token"]},
        }

        code = self._mint_token(_branch_id, "authorization_code", grant)
        assert code.usage_rules == {
            "max_usage": 1,
            "supports_minting": ["access_token", "refresh_token", "id_token"],
            "expires_in": 300,
        }

        token = self._mint_token(_branch_id, "access_token", grant, code)
        assert token.usage_rules == {"expires_in": 3600}

        refresh_token = self._mint_token(_branch_id, "refresh_token", grant, code)
        assert refresh_token.usage_rules == {
            "supports_minting": ["access_token", "refresh_token", "id_token"]
        }

    def test_token_usage_authz(self):
        grant_config = {
            "usage_rules": {
                "authorization_code": {
                    "supports_minting": ["access_token"],
                    "max_usage": 1,
                    "expires_in": 120,
                },
                "access_token": {"expires_in": 600},
            },
            "expires_in": 43200,
        }

        self.endpoint_context.authz = AuthzHandling(
            self.server.get_endpoint_context, grant_config=grant_config
        )

        self.endpoint_context.cdb["client_1"] = {}

        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")

        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        grant = self.session_manager[_branch_id]

        code = self._mint_token(_branch_id, "authorization_code", grant)
        assert code.usage_rules == {
            "max_usage": 1,
            "supports_minting": ["access_token"],
            "expires_in": 120,
        }

        token = self._mint_token(_branch_id, "access_token", grant, code)
        assert token.usage_rules == {"expires_in": 600}

        # Only allowed to mint access_tokens using the authorization_code
        with pytest.raises(MintingNotAllowed):
            self._mint_token(_branch_id, "refresh_token", grant, code)

    def test_token_usage_client_config(self):
        grant_config = {
            "usage_rules": {
                "authorization_code": {
                    "supports_minting": ["access_token"],
                    "max_usage": 1,
                    "expires_in": 120,
                },
                "access_token": {"expires_in": 600},
                "refresh_token": {},
            },
            "expires_in": 43200,
        }

        self.endpoint_context.authz = AuthzHandling(
            self.server.get_endpoint_context, grant_config=grant_config
        )

        # Change expiration time for the code and allow refresh tokens for this
        # specific client
        self.endpoint_context.cdb["client_1"] = {
            "token_usage_rules": {
                "authorization_code": {
                    "expires_in": 600,
                    "supports_minting": ["access_token", "refresh_token"],
                },
                "refresh_token": {"supports_minting": ["access_token"]},
            }
        }

        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")

        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        grant = self.session_manager[_branch_id]

        code = self._mint_token(_branch_id, "authorization_code", grant)
        assert code.usage_rules == {
            "max_usage": 1,
            "supports_minting": ["access_token", "refresh_token"],
            "expires_in": 600,
        }

        token = self._mint_token(_branch_id, "access_token", grant, code)
        assert token.usage_rules == {"expires_in": 600}

        refresh_token = self._mint_token(_branch_id, "refresh_token", grant, code)
        assert refresh_token.usage_rules == {"supports_minting": ["access_token"]}

        # Test with another client

        self.endpoint_context.cdb["client_2"] = {}

        token_usage_rules = self.endpoint_context.authz.usage_rules("client_2")

        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_2",
            token_usage_rules=token_usage_rules,
        )
        grant = self.session_manager[_branch_id]
        code = self._mint_token(_branch_id, "authorization_code", grant)
        # Not allowed to mint refresh token for this client
        with pytest.raises(MintingNotAllowed):
            self._mint_token(_branch_id, "refresh_token", grant, code)

        # test revoke token
        self.session_manager.revoke_token(_branch_id, code.value, recursive=1)

    def test_authentication_events(self):
        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        res = self.session_manager.get_authentication_events(_branch_id)

        assert isinstance(res[0], AuthnEvent)

        res = self.session_manager.get_authentication_events(
            self.session_manager.encrypted_branch_id("diana","client_1"))

        assert isinstance(res[0], AuthnEvent)

        try:
            self.session_manager.get_authentication_events(
                self.session_manager.encrypted_branch_id("diana"),
            )
        except AttributeError:
            pass
        else:
            raise Exception("get_authentication_events MUST return a list of AuthnEvent")

    def test_user_info(self):
        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        self.session_manager.get_user_info(self.session_manager.encrypted_branch_id("diana"))

    def test_revoke_client_session(self):
        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        self.session_manager.revoke_client_session(_branch_id)

    def test_revoke_grant(self):
        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        grant = self.session_manager[_branch_id]
        self.session_manager.revoke_grant(_branch_id)

    def test_revoke_dependent(self):
        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        grant = self.session_manager[_branch_id]

        code = self._mint_token(_branch_id, "authorization_code", grant)
        token = self._mint_token(_branch_id, "access_token", grant, code)

        grant.remove_inactive_token = True
        grant.revoke_token(value=token.value)
        assert len(grant.issued_token) == 1
        assert grant.issued_token[0].token_class == "authorization_code"

    def test_grants(self):
        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        res = self.session_manager.grants(_branch_id)

        assert isinstance(res, list)

        res = self.session_manager.grants(path=["diana", "client_1"])

        assert isinstance(res, list)

        self.session_manager.grants(path=["diana"])

        # and now add_grant
        grant = self.session_manager[_branch_id]
        grant_kwargs = grant.parameter
        for i in ("not_before", "used", "usage_rules"):
            grant_kwargs.pop(i)
        self.session_manager.add_grant(["diana", "client_1"], **grant_kwargs)

    def test_find_latest_idtoken(self):
        token_usage_rules = self.endpoint_context.authz.usage_rules("client_1")
        _branch_id = self.session_manager.create_session(
            authentication_event=self.authn_event,
            authorization_request=AUTH_REQ,
            user_id="diana",
            client_id="client_1",
            token_usage_rules=token_usage_rules,
        )
        grant = self.session_manager[_branch_id]

        code = self._mint_token(_branch_id, "authorization_code", grant)
        id_token_1 = self._mint_token(_branch_id, "id_token", grant)

        refresh_token = self._mint_token(_branch_id, "refresh_token", grant, code)
        id_token_2 = self._mint_token(_branch_id, "id_token", grant, code)

        _jwt1 = factory(id_token_1.value)
        _jwt2 = factory(id_token_2.value)
        assert _jwt1.jwt.payload()["sid"] == _jwt2.jwt.payload()["sid"]

        assert id_token_1.session_id == id_token_2.session_id

        idt = grant.last_issued_token_of_type("id_token")

        assert idt.session_id == id_token_2.session_id

        id_token_3 = self._mint_token(_branch_id, "id_token", grant, refresh_token)

        idt = grant.last_issued_token_of_type("id_token")

        assert idt.session_id == id_token_3.session_id
