# Safety Policy

Created by zyr0x

RevForge is for legal CTF training, classroom labs, and authorized reverse engineering practice.

RevForge does not generate malware. It does not generate persistence, destructive code, credential collection, network callbacks, privilege escalation, stealth, antivirus evasion, or exploitation behavior.

Generated binaries are local crackme programs. They read a candidate flag from command-line arguments, standard input, or a local Android/browser UI, validate it in memory, and print or display success or failure.

Allowed generated behavior:

- Local string, byte, arithmetic, state-machine, or toy-VM validation.
- Educational obfuscation suitable for CTF crackmes.
- Fake strings and decoy flags that remain harmless static data.
- Build scripts that compile the generated challenge.

Disallowed generated behavior:

- File theft, credential prompts, browser/token collection, or secret scanning.
- Network access, callbacks, beaconing, downloaders, or command execution.
- Persistence, startup installation, service creation, or scheduled tasks.
- Privilege escalation, kernel interaction, or exploitation.
- Destructive file, disk, registry, or device behavior.
- Real anti-analysis, sandbox evasion, or antivirus bypass behavior.

If a proposed template needs behavior outside local input validation, it does not belong in RevForge.

