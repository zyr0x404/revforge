# Safety Policy

RevForge is for legal CTF training and authorized reverse engineering practice.

RevForge does not generate malware. It does not generate persistence, destructive code, credential collection, network callbacks, privilege escalation, stealth, antivirus evasion, or exploitation behavior.

Generated binaries are local validators. They only read local challenge artifacts and user-provided input, validate in memory, and print or display success or failure.

Allowed generated behavior:

- Local string, byte, arithmetic, state-machine, file-format, constraint, pipeline, or VM validation.
- Educational obfuscation suitable for advanced CTF reversing.
- Neutral decoy strings that remain harmless static data.
- Build scripts that compile the generated challenge.

Disallowed generated behavior:

- File theft, credential prompts, browser/token collection, or secret scanning.
- Network access, callbacks, beaconing, downloaders, or command execution.
- Persistence, startup installation, service creation, or scheduled tasks.
- Privilege escalation, kernel interaction, or exploitation.
- Destructive file, disk, registry, or device behavior.
- Real anti-analysis, sandbox evasion, or antivirus bypass behavior.

If a proposed template needs behavior outside local artifact parsing and input validation, it does not belong in RevForge.
