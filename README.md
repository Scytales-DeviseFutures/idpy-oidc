# idpyoidc

![CI build](https://github.com/IdentityPython/idpy-oidc/workflows/idpy-oidc/badge.svg)
![pypi](https://img.shields.io/pypi/v/idpyoidc.svg)
[![Downloads](https://pepy.tech/badge/idpyoidc)](https://pepy.tech/project/idpyoidc)
[![Downloads](https://pepy.tech/badge/idpyoidc/week)](https://pepy.tech/project/idpyoidc)
![License](https://img.shields.io/badge/license-Apache%202-blue.svg)

This project is a Python implementation of everything OpenID Connect and OAuth2.

## Introduction

idpyoidc is the 2nd layer in the JwtConnect stack (cryptojwt, idpyoidc).
As OIDC OP Idpy implements the following standards:

* [OpenID Connect Core 1.0 incorporating errata set 1](https://openid.net/specs/openid-connect-core-1_0.html)
* [Web Finger](https://openid.net/specs/openid-connect-discovery-1_0.html#IssuerDiscovery)
* [OpenID Connect Discovery 1.0 incorporating errata set 1](https://openid.net/specs/openid-connect-discovery-1_0.html)
* [OpenID Connect Dynamic Client Registration 1.0 incorporating errata set 1](https://openid.net/specs/openid-connect-registration-1_0.html)
* [OpenID Connect Session Management 1.0](https://openid.net/specs/openid-connect-session-1_0.html)
* [OpenID Connect Back-Channel Logout 1.0](https://openid.net/specs/openid-connect-backchannel-1_0.html)
* [OpenID Connect Front-Channel Logout 1.0](https://openid.net/specs/openid-connect-frontchannel-1_0.html)
* [OAuth2 Token introspection](https://tools.ietf.org/html/rfc7662)
* [OAuth 2.0 Form Post Response Mode](https://openid.net/specs/oauth-v2-form-post-response-mode-1_0.html)

It also comes with the following `add_on` modules.

* Custom scopes, that extends [OIDC standard ScopeClaims](https://openid.net/specs/openid-connect-core-1_0.html#ScopeClaims)
* [Proof Key for Code Exchange by OAuth Public Clients (PKCE)](https://tools.ietf.org/html/rfc7636)
* [OAuth2 PAR](https://datatracker.ietf.org/doc/html/rfc9126)
* [OAuth2 RAR](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-rar)
* [OAuth2 DPoP](https://tools.ietf.org/id/draft-fett-oauth-dpop-04.html)
* [OAuth 2.0 Authorization Server Issuer Identification](https://datatracker.ietf.org/doc/draft-ietf-oauth-iss-auth-resp)

## Usage 

If you want to add or replace functionality the official documentation should be able to tell you how.
If you are just going to build a standard OP you only have to understand how to write your configuration file.
In `example/` folder you'll find some complete examples based on flask and django.

Please read the [Official Documentation](https://idpyoidc.readthedocs.io/) for getting usage examples and further informations.

## Contribute

Your contribution is welcome, no question is useless and no answer is obvious, we need you.

#### Contribute as end user

Please open an issue if you've discoveerd a bug or if you want to ask some features.

#### Contribute as developer

Please open your Pull Requests on the __develop__ branch. 
Please consider the following branches:

 - __main__: where we merge the code before tag a new stable release.
 - __develop__: where we push our code during development.
 - __other-custom-name__: where a new feature/contribution/bugfix will be handled, revisioned and then merged to dev branch.

## Certifications
[![OIDC Certification](https://openid.net/wordpress-content/uploads/2016/04/oid-l-certification-mark-l-rgb-150dpi-90mm-300x157.png)](https://www.certification.openid.net/plan-detail.html?public=true&plan=7p3iPQmff6Ohv)

## License

The entire project code is open sourced and therefore licensed under the [Apache 2.0](https://en.wikipedia.org/wiki/Apache_License).
