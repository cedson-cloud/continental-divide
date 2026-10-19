# Security

## Reporting a vulnerability

Please report security problems privately, through GitHub's private vulnerability
reporting. Open the [Security tab](https://github.com/cedson-cloud/continental-divide/security)
and click **Report a vulnerability**, or go straight to the
[report form](https://github.com/cedson-cloud/continental-divide/security/advisories/new).
Please keep the details out of pull requests and anywhere else public until a fix is out.

A useful report says what you found, how to reproduce it, and what someone could do with it.

This is a one-person project, so replies are best effort. I'll tell you whether I can
reproduce the problem and what I plan to do about it, and credit you in the fix if you'd
like.

## Scope

Fixes go to the `main` branch and the public demo at <https://continental-divide.vercel.app>,
which runs from it. There are no other supported versions.

The demo holds no real customer data. Each visitor's sandbox holds only what that visitor
typed, and is deleted after seven days without use. The reports I most want to hear about:

- one visitor reading or changing another visitor's sandbox
- getting around the request, rate or spending limits
- reaching the backend without going through the site
- editing or deleting a row in the audit log
- a secret or credential anywhere in the repository or its history

Please don't run load tests or automated scanners against the live demo. It runs on a small
daily budget, and a flood of requests uses it up and stops the demo working for everyone.
