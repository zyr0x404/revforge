# Examples

Generate examples locally:

```bash
revforge new --name baby1 --difficulty baby --out ./examples
revforge new --name multi1 --difficulty medium --template multi-stage --out ./examples
revforge new --name firmware_gate --difficulty hard --profile qualifier --style terminal --family terminal_firmware_blob --target elf --out ./examples
revforge new --name finals_boss --difficulty super-hard --profile finals --style terminal --family terminal_hybrid_finals --target elf --out ./examples
```

The `examples/` directory is intentionally kept light in git so generated binaries and challenge bundles do not bloat the repository.
