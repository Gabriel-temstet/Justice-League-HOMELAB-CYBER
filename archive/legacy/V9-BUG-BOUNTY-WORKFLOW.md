# V9 Bug Bounty Workflow

The V9 lab now includes a repeatable authorized workflow:

`Scope -> Subdomains -> DNS -> HTTP -> Crawl -> URL history -> Nuclei/Dalfox -> Evidence -> Report`

Default mode is passive. Active mode is an explicit operator choice and remains behind the scope guard. The lab does not attempt to bypass authentication, evade controls, persist on targets, or weaponize findings.
