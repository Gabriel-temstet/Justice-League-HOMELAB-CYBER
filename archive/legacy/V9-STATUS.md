# V9 STATUS

V9 adds a dedicated Bug Bounty / AppSec container to the Justice League stack.

Implemented:
- isolated Compose service
- explicit target allow-list
- execution wrapper with scope enforcement
- broad reconnaissance/web/AppSec toolkit
- persistent workspace/results volumes
- SecLists wordlists
- deploy and interactive shell scripts
- documentation and safe defaults

Not claimed as automatic:
- bug-bounty program authorization
- scope interpretation from a third-party program page
- API credentials
- CAPTCHA bypass, stealth/evasion, persistence, destructive exploitation
- physical network configuration

The image must be built on the target host because tool releases and package repositories are external build inputs.
