"""Terminal-style challenge families with local-only artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Any

from .recipes import ChallengeRecipe
from .utils import BANNER, CREATED_BY, c_array, c_string


@dataclass(frozen=True)
class TerminalRender:
    source: str
    solution: str
    writeup: str
    artifacts: dict[str, bytes]


FAMILY_ALIASES = {
    "qualifier_vm": "terminal_license_vm",
    "qualifier_constraints": "terminal_constraints_pack",
    "qualifier_state_machine": "terminal_firmware_blob",
    "qualifier_transform_pipeline": "terminal_signal_pipeline",
}

NEUTRAL_DECOYS = [
    "debug route disabled",
    "invalid signal block",
    "checksum mismatch",
    "firmware gate closed",
    "state transition rejected",
    "calibration failed",
    "trace segment rejected",
    "license window expired",
]


def is_terminal_family(family: str) -> bool:
    return family.startswith("terminal_") or family.startswith("qualifier_")


def effective_family(family: str) -> str:
    return FAMILY_ALIASES.get(family, family)


def prepare_terminal_recipe(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> ChallengeRecipe:
    family = effective_family(recipe.template_family)
    recipe.style = "terminal"
    recipe.family = recipe.template_family
    recipe.fake_strings = rng.sample(NEUTRAL_DECOYS, k=4)
    recipe.success_message = "Accepted. Verification state reached."
    recipe.failure_message = "Rejected. Verification state mismatch."
    recipe.complexity_budget = _complexity_budget(recipe)
    if family == "terminal_firmware_blob":
        _prep_firmware_blob(recipe, rng, flag_bytes)
    elif family == "terminal_license_vm":
        _prep_license_vm(recipe, rng, flag_bytes)
    elif family == "terminal_signal_pipeline":
        _prep_signal_pipeline(recipe, rng, flag_bytes)
    elif family == "terminal_constraints_pack":
        _prep_constraints_pack(recipe, rng, flag_bytes)
    elif family == "terminal_hybrid_finals":
        _prep_hybrid_finals(recipe, rng, flag_bytes)
    else:
        raise ValueError(f"terminal family is not implemented: {recipe.template_family}")
    return recipe


def render_terminal(recipe: ChallengeRecipe) -> TerminalRender:
    family = effective_family(recipe.template_family)
    if family == "terminal_firmware_blob":
        return TerminalRender(_firmware_source(recipe), _firmware_solver(recipe), _terminal_writeup(recipe), _artifacts(recipe))
    if family == "terminal_license_vm":
        return TerminalRender(_license_source(recipe), _license_solver(recipe), _terminal_writeup(recipe), _artifacts(recipe))
    if family == "terminal_signal_pipeline":
        return TerminalRender(_signal_source(recipe), _signal_solver(recipe), _terminal_writeup(recipe), _artifacts(recipe))
    if family == "terminal_constraints_pack":
        return TerminalRender(_constraints_source(recipe), _constraints_solver(recipe), _terminal_writeup(recipe), _artifacts(recipe))
    if family == "terminal_hybrid_finals":
        return TerminalRender(_hybrid_source(recipe), _hybrid_solver(recipe), _terminal_writeup(recipe), _artifacts(recipe))
    raise ValueError(f"terminal renderer is not implemented: {recipe.template_family}")


def _complexity_budget(recipe: ChallengeRecipe) -> int:
    if recipe.profile == "finals":
        return 10
    if recipe.difficulty == "super-hard":
        return 9
    if recipe.difficulty == "hard":
        return 8
    if recipe.difficulty == "medium":
        return 6
    return 4


def _prep_firmware_blob(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    n = len(flag_bytes)
    key = rng.randint(1, 255)
    perm = list(range(n))
    rng.shuffle(perm)
    xors = [rng.randint(1, 255) for _ in range(n)]
    adds = [rng.randint(0, 255) for _ in range(n)]
    rots = [rng.randint(1, 7) for _ in range(n)]
    targets = []
    for i, pos in enumerate(perm):
        v = _rotl8(((flag_bytes[pos] ^ xors[i]) + adds[i]) & 0xFF, rots[i])
        targets.append(v ^ ((key + i * 17) & 0xFF))
    payload = bytearray(b"RFFW1")
    payload.extend([n, key])
    payload.extend(perm)
    payload.extend(xors)
    payload.extend(adds)
    payload.extend(rots)
    payload.extend(targets)
    recipe.encoding_chain = ["local blob format", "permuted transform table", "encoded constants"]
    recipe.checker_type = "terminal-firmware-blob"
    recipe.artifact_files = ["firmware.blob"]
    recipe.terminal_commands = ["--help", "info", "verify", "check", "inspect"]
    recipe.technique_mix = ["custom local blob format", "encoded tables", "transform pipeline"]
    recipe.operations = ["file", "xxd", "strings", "objdump", "readelf", "gdb", "Python parsing"]
    recipe.transformations = ["chunk permutation", "xor/add/rotate", "encoded table compare"]
    recipe.constants.update(
        {
            "artifact_name": "firmware.blob",
            "artifact_magic": "RFFW1",
            "artifact_bytes": list(payload),
            "encoded_constant_count": n * 4,
            "constraint_count": 0,
            "bytecode_length": 0,
            "artifact_count": 1,
        }
    )
    recipe.checker_logic = "The binary loads firmware.blob, decodes transform tables, and validates a candidate through table-driven byte checks."


def _prep_license_vm(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    finals = recipe.profile == "finals"
    op_names = [
        "LOAD",
        "XOR",
        "ADD",
        "SUB",
        "ROL",
        "ROR",
        "MIX",
        "CMP",
        "HASH",
        "JMP",
        "JNZ",
        "HALT",
        "NOP",
        "AND",
        "OR",
        "SWAP",
        "SEED",
        "CHK",
    ]
    op_count = 18 if finals else 12
    opcodes = rng.sample(range(1, 245), op_count)
    op = {name: opcodes[i] for i, name in enumerate(op_names[:op_count])}
    initial_state = rng.randint(0, 0xFFFFFFFF)
    state = initial_state
    program: list[int] = []
    instructions = []
    for i, byte in enumerate(flag_bytes):
        xk = rng.randint(1, 255)
        add = rng.randint(0, 255)
        sub = rng.randint(0, 255)
        rol = rng.randint(1, 7)
        ror = rng.randint(1, 7)
        mix = rng.randint(1, 255)
        v = byte
        v ^= xk
        v = (v + add) & 0xFF
        v = (v - sub) & 0xFF
        v = _rotl8(v, rol)
        v = _ror8(v, ror)
        v ^= mix
        state = ((state ^ v) * 16777619 + i + mix) & 0xFFFFFFFF
        program.extend([op["LOAD"], i, op["XOR"], xk, op["ADD"], add, op["SUB"], sub, op["ROL"], rol, op["ROR"], ror, op["MIX"], mix, op["CMP"], v, op["HASH"], mix])
        instructions.append({"index": i, "xor": xk, "add": add, "sub": sub, "rol": rol, "ror": ror, "mix": mix, "expected": v})
    program.append(op["HALT"])
    program.extend(_u32(state))
    min_len = 350 if finals else 180
    decoy_ops = opcodes[:]
    while len(program) < min_len:
        program.extend([rng.choice(decoy_ops), rng.randint(0, 255)])
    key = rng.randint(1, 255)
    encoded = [(b ^ ((key + i * 13) & 0xFF)) & 0xFF for i, b in enumerate(program)]
    payload = bytearray(b"RFLIC1")
    payload.extend([len(flag_bytes), op_count, key])
    payload.extend(_u32(initial_state))
    payload.extend(opcodes)
    payload.extend(_u16(len(encoded)))
    payload.extend(encoded)
    recipe.encoding_chain = ["encoded VM bytecode", "randomized opcode map", "final state hash", "decoy bytecode"]
    recipe.checker_type = "terminal-license-vm"
    recipe.artifact_files = ["license.dat"]
    recipe.terminal_commands = ["--help", "info", "verify", "check", "unlock"]
    recipe.technique_mix = ["custom VM", "encoded bytecode", "randomized dispatch", "state hash"]
    recipe.operations = op_names[:op_count]
    recipe.transformations = ["decode bytecode", "execute local VM", "final state/hash gate"]
    recipe.stages = instructions
    recipe.constants.update(
        {
            "artifact_name": "license.dat",
            "artifact_magic": "RFLIC1",
            "artifact_bytes": list(payload),
            "bytecode_length": len(encoded),
            "encoded_constant_count": len(encoded) + op_count,
            "constraint_count": 0,
            "artifact_count": 1,
            "vm_opcode_count": op_count,
        }
    )
    recipe.checker_logic = "The binary loads license.dat, decodes randomized VM bytecode, and accepts only when VM comparisons and the final state hash match."


def _prep_signal_pipeline(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    n = len(flag_bytes)
    chunk_count = min(6, max(3, n // 5))
    cuts = sorted(rng.sample(range(1, n), chunk_count - 1)) if n > chunk_count else []
    starts = [0, *cuts]
    ends = [*cuts, n]
    lengths = [end - start for start, end in zip(starts, ends)]
    order = list(range(len(lengths)))
    rng.shuffle(order)
    permuted_positions: list[int] = []
    for chunk_index in order:
        permuted_positions.extend(range(starts[chunk_index], ends[chunk_index]))
    key = rng.randint(1, 255)
    xors = [rng.randint(1, 255) for _ in range(n)]
    adds = [rng.randint(0, 255) for _ in range(n)]
    rots = [rng.randint(1, 7) for _ in range(n)]
    table_seed = rng.randint(1, 255)
    table = list(range(256))
    rng.shuffle(table)
    targets = []
    transformed = []
    for i, pos in enumerate(permuted_positions):
        v = _rotl8(((flag_bytes[pos] ^ xors[i]) + adds[i]) & 0xFF, rots[i])
        v = table[v]
        transformed.append(v)
        targets.append(v ^ ((key + i * 11) & 0xFF))
    checksum = _rolling_hash(transformed, 0xA5A50000 | table_seed)
    encoded_table = [value ^ ((key + i * 3) & 0xFF) for i, value in enumerate(table)]
    payload = bytearray(b"RFSIG1")
    payload.extend([n, key, len(lengths), table_seed])
    payload.extend(lengths)
    payload.extend(order)
    payload.extend(xors)
    payload.extend(adds)
    payload.extend(rots)
    payload.extend(encoded_table)
    payload.extend(targets)
    payload.extend(_u32(checksum))
    recipe.encoding_chain = ["chunk permutation", "xor/add/rotate", "lookup table", "rolling checksum"]
    recipe.checker_type = "terminal-signal-pipeline"
    recipe.artifact_files = ["signal.dat"]
    recipe.terminal_commands = ["--help", "scan", "verify"]
    recipe.technique_mix = ["custom file parsing", "transform pipeline", "rolling hash", "encoded lookup table"]
    recipe.operations = ["xxd", "strings", "objdump", "Python scripting"]
    recipe.transformations = ["chunk permutation", "XOR/add/rotate", "table lookup", "rolling hash"]
    recipe.constants.update(
        {
            "artifact_name": "signal.dat",
            "artifact_magic": "RFSIG1",
            "artifact_bytes": list(payload),
            "bytecode_length": 0,
            "encoded_constant_count": n * 4 + 256,
            "constraint_count": 0,
            "artifact_count": 1,
        }
    )
    recipe.checker_logic = "The binary scans signal.dat, reconstructs a chunk order and transform table, then validates the candidate through a staged signal pipeline."


def _prep_constraints_pack(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    target_count = 80 if recipe.profile == "finals" or recipe.difficulty == "super-hard" else 40
    records: list[list[int]] = []
    n = len(flag_bytes)
    for i, byte in enumerate(flag_bytes):
        mult = rng.choice([3, 5, 7, 11, 17, 19, 23, 29, 31, 37])
        add = rng.randint(0, 256)
        records.append([4, i, mult, add, 257, ((byte * mult) + add) % 257])
    while len(records) < target_count:
        typ = rng.choice([1, 2, 3, 4, 5, 6])
        if typ == 1:
            i, j = rng.sample(range(n), 2)
            records.append([1, i, j, flag_bytes[i] + flag_bytes[j]])
        elif typ == 2:
            i, j = rng.sample(range(n), 2)
            records.append([2, i, j, flag_bytes[i] ^ flag_bytes[j]])
        elif typ == 3:
            i, j = rng.sample(range(n), 2)
            rot = rng.randint(1, 7)
            records.append([3, i, j, rot, _rotl8(flag_bytes[i], rot) ^ flag_bytes[j]])
        elif typ == 4:
            i = rng.randrange(n)
            mult = rng.choice([3, 5, 7, 11, 17, 19, 23, 29, 31, 37])
            add = rng.randint(0, 256)
            records.append([4, i, mult, add, 257, ((flag_bytes[i] * mult) + add) % 257])
        elif typ == 5:
            i, j, k = rng.sample(range(n), 3)
            records.append([5, i, j, k, (flag_bytes[i] * 3 + flag_bytes[j] * 5 + flag_bytes[k] * 7) % 257])
        else:
            start = rng.randrange(0, max(1, n - 2))
            length = rng.randint(2, min(6, n - start))
            seed = rng.randint(0, 255)
            records.append([6, start, length, seed, _rolling_hash(flag_bytes[start : start + length], 0xC0DE0000 | seed)])
    key = rng.randint(1, 255)
    payload = bytearray(b"RFCON1")
    payload.extend([n, key])
    payload.extend(_u16(len(records)))
    for record in records:
        payload.extend([record[0], len(record) - 1])
        for value in record[1:]:
            payload.extend(_u32(value))
    encoded = bytearray(payload[:10])
    encoded.extend(value ^ ((key + i * 5) & 0xFF) for i, value in enumerate(payload[10:]))
    recipe.encoding_chain = ["encoded constraint pack", "pair relations", "triple relations", "chunk hashes"]
    recipe.checker_type = "terminal-constraints-pack"
    recipe.artifact_files = ["constraints.pack"]
    recipe.terminal_commands = ["--help", "verify", "check", "inspect"]
    recipe.technique_mix = ["constraint system", "encoded local pack", "chunk hash gates"]
    recipe.operations = ["z3-compatible equations", "pure Python fallback", "file parser"]
    recipe.transformations = ["sum constraints", "xor constraints", "rotate/xor constraints", "modular constraints", "triple relations"]
    recipe.constants.update(
        {
            "artifact_name": "constraints.pack",
            "artifact_magic": "RFCON1",
            "artifact_bytes": list(encoded),
            "bytecode_length": 0,
            "encoded_constant_count": len(encoded),
            "constraint_count": len(records),
            "artifact_count": 1,
        }
    )
    recipe.checker_logic = "The binary loads constraints.pack and validates a generated byte-constraint system over the candidate."


def _prep_hybrid_finals(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    n = len(flag_bytes)
    vm_key = rng.randint(1, 255)
    opcodes = rng.sample(range(1, 245), 18)
    op = {"LOAD": opcodes[0], "XOR": opcodes[1], "ADD": opcodes[2], "ROL": opcodes[3], "MIX": opcodes[4], "CMP": opcodes[5], "HASH": opcodes[6], "HALT": opcodes[7], "NOP": opcodes[8]}
    state = rng.randint(0, 0xFFFFFFFF)
    initial_state = state
    program: list[int] = []
    for i, byte in enumerate(flag_bytes):
        xk = rng.randint(1, 255)
        add = rng.randint(0, 255)
        rot = rng.randint(1, 7)
        mix = rng.randint(1, 255)
        v = _rotl8(((byte ^ xk) + add) & 0xFF, rot) ^ mix
        state = ((state ^ v) * 16777619 + i + mix) & 0xFFFFFFFF
        program.extend([op["LOAD"], i, op["XOR"], xk, op["ADD"], add, op["ROL"], rot, op["MIX"], mix, op["CMP"], v, op["HASH"], mix])
    program.append(op["HALT"])
    program.extend(_u32(state))
    while len(program) < 380:
        program.extend([op["NOP"], rng.randint(0, 255)])
    encoded_vm = [(b ^ ((vm_key + i * 7) & 0xFF)) & 0xFF for i, b in enumerate(program)]
    cons = []
    for i, byte in enumerate(flag_bytes):
        mult = rng.choice([3, 5, 7, 11, 17, 19, 23, 29, 31, 37])
        add = rng.randint(0, 256)
        cons.append([i, mult, add, ((byte * mult) + add) % 257])
    while len(cons) < 80:
        i = rng.randrange(n)
        mult = rng.choice([3, 5, 7, 11, 17, 19, 23, 29, 31, 37])
        add = rng.randint(0, 256)
        cons.append([i, mult, add, ((flag_bytes[i] * mult) + add) % 257])
    pipe_key = rng.randint(1, 255)
    pipe_xor = [rng.randint(1, 255) for _ in range(n)]
    pipe_add = [rng.randint(0, 255) for _ in range(n)]
    pipe_rot = [rng.randint(1, 7) for _ in range(n)]
    pipe_targets = []
    pipe_values = []
    for i, byte in enumerate(flag_bytes):
        v = _rotl8(((byte ^ pipe_xor[i]) + pipe_add[i]) & 0xFF, pipe_rot[i])
        pipe_values.append(v)
        pipe_targets.append(v ^ ((pipe_key + i * 19) & 0xFF))
    pipe_hash = _rolling_hash(pipe_values, 0xF17A1000 | pipe_key)
    payload = bytearray(b"RFHYB1")
    payload.extend([n, vm_key, pipe_key, 18])
    payload.extend(_u32(initial_state))
    payload.extend(opcodes)
    payload.extend(_u16(len(encoded_vm)))
    payload.extend(encoded_vm)
    payload.extend(_u16(len(cons)))
    for item in cons:
        for value in item:
            payload.extend(_u32(value))
    payload.extend(pipe_xor)
    payload.extend(pipe_add)
    payload.extend(pipe_rot)
    payload.extend(pipe_targets)
    payload.extend(_u32(pipe_hash))
    recipe.encoding_chain = ["custom local capsule", "VM bytecode", "constraint system", "transform pipeline", "rolling hash"]
    recipe.checker_type = "terminal-hybrid-finals"
    recipe.artifact_files = ["capsule.bin"]
    recipe.terminal_commands = ["--help", "info", "verify", "check", "run"]
    recipe.technique_mix = ["custom local blob format", "VM bytecode", "constraint system", "transform pipeline", "rolling hash gates"]
    recipe.operations = ["file", "xxd", "strings", "readelf", "objdump", "gdb", "Python emulator", "constraint solving"]
    recipe.transformations = ["encoded VM", "modular constraints", "xor/add/rotate pipeline", "rolling hash"]
    recipe.constants.update(
        {
            "artifact_name": "capsule.bin",
            "artifact_magic": "RFHYB1",
            "artifact_bytes": list(payload),
            "bytecode_length": len(encoded_vm),
            "encoded_constant_count": len(payload),
            "constraint_count": len(cons),
            "artifact_count": 1,
        }
    )
    recipe.checker_logic = "The binary loads capsule.bin and requires the candidate to pass VM, constraint, transform, and rolling-hash gates."


def _artifacts(recipe: ChallengeRecipe) -> dict[str, bytes]:
    return {recipe.constants["artifact_name"]: bytes(recipe.constants["artifact_bytes"])}


def _u16(value: int) -> list[int]:
    return [value & 0xFF, (value >> 8) & 0xFF]


def _u32(value: int) -> list[int]:
    return [value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, (value >> 24) & 0xFF]


def _rotl8(value: int, amount: int) -> int:
    amount &= 7
    return ((value << amount) | (value >> (8 - amount))) & 0xFF


def _ror8(value: int, amount: int) -> int:
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xFF


def _rolling_hash(values: list[int], seed: int) -> int:
    h = seed & 0xFFFFFFFF
    for value in values:
        h = ((h ^ value) * 16777619 + 0x9E3779B9) & 0xFFFFFFFF
        h ^= h >> 13
    return h & 0xFFFFFFFF


def _common_c_helpers() -> str:
    return """static unsigned int rf_rotl8(unsigned int value, unsigned int amount) {
    amount &= 7u;
    return ((value << amount) | (value >> (8u - amount))) & 0xFFu;
}

static unsigned int rf_ror8(unsigned int value, unsigned int amount) {
    amount &= 7u;
    return ((value >> amount) | (value << (8u - amount))) & 0xFFu;
}

static uint32_t rf_rd32(const unsigned char *p) {
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8u) | ((uint32_t)p[2] << 16u) | ((uint32_t)p[3] << 24u);
}

static unsigned int rf_rd16(const unsigned char *p) {
    return (unsigned int)p[0] | ((unsigned int)p[1] << 8u);
}

static uint32_t rf_roll_hash_bytes(const unsigned char *data, size_t len, uint32_t seed) {
    uint32_t h = seed;
    for (size_t i = 0; i < len; i++) {
        h = ((h ^ data[i]) * 16777619u + 0x9E3779B9u) & 0xFFFFFFFFu;
        h ^= h >> 13u;
    }
    return h;
}

static unsigned char *rf_read_file(const char *path, size_t max_len, size_t *out_len) {
    FILE *fp = fopen(path, "rb");
    unsigned char *buf;
    long end;
    size_t got;
    if (!fp) return NULL;
    if (fseek(fp, 0, SEEK_END) != 0) { fclose(fp); return NULL; }
    end = ftell(fp);
    if (end < 0 || (size_t)end > max_len) { fclose(fp); return NULL; }
    rewind(fp);
    buf = (unsigned char *)malloc((size_t)end + 1u);
    if (!buf) { fclose(fp); return NULL; }
    got = fread(buf, 1u, (size_t)end, fp);
    fclose(fp);
    if (got != (size_t)end) { free(buf); return NULL; }
    buf[got] = 0;
    *out_len = got;
    return buf;
}

static int rf_streq(const char *a, const char *b) {
    return strcmp(a, b) == 0;
}

static int rf_file_exists(const char *path) {
    FILE *fp = fopen(path, "rb");
    if (!fp) return 0;
    fclose(fp);
    return 1;
}

static const char *rf_resolve_default_artifact(const char *prog, char *buf, size_t buf_len) {
    const char *slash;
    size_t dir_len;
    int written;
    if (rf_file_exists(rf_default_artifact)) return rf_default_artifact;
    slash = strrchr(prog, '/');
    if (!slash) slash = strrchr(prog, '\\\\');
    if (!slash) return rf_default_artifact;
    dir_len = (size_t)(slash - prog);
    written = snprintf(buf, buf_len, "%.*s/../%s", (int)dir_len, prog, rf_default_artifact);
    if (written > 0 && (size_t)written < buf_len && rf_file_exists(buf)) return buf;
    written = snprintf(buf, buf_len, "%.*s/%s", (int)dir_len, prog, rf_default_artifact);
    if (written > 0 && (size_t)written < buf_len && rf_file_exists(buf)) return buf;
    return rf_default_artifact;
}
"""


def _terminal_fake_string_block(recipe: ChallengeRecipe) -> str:
    values = recipe.fake_strings + recipe.fake_flags
    if not values:
        return "static void rf_touch_terminal_decoys(void) {}\n"
    lines = ",\n".join(f"    {c_string(value)}" for value in values)
    return f"""static const char *rf_terminal_decoys[] = {{
{lines}
}};

static void rf_touch_terminal_decoys(void) {{
    volatile unsigned int total = 0;
    for (unsigned int i = 0; i < (unsigned int)(sizeof(rf_terminal_decoys) / sizeof(rf_terminal_decoys[0])); i++) {{
        total += (unsigned char)rf_terminal_decoys[i][0];
    }}
    if (total == 0xFFFFFFFFu) {{
        puts(rf_terminal_decoys[0]);
    }}
}}
"""


def _source_preamble(recipe: ChallengeRecipe) -> str:
    return f"""/* Created by {CREATED_BY} */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *rf_banner = {c_string(BANNER)};
static const char *rf_default_artifact = {c_string(recipe.constants["artifact_name"])};

{_common_c_helpers()}
{_terminal_fake_string_block(recipe)}
"""


def _main_source(recipe: ChallengeRecipe, validator_name: str, check_name: str, extra_commands: str, help_text: str) -> str:
    return f"""
static void rf_help(const char *prog) {{
    printf("usage: %s <command> [argument]\\n", prog);
{help_text}
}}

int main(int argc, char **argv) {{
    char artifact_buf[1024] = {{0}};
    const char *artifact_path = rf_resolve_default_artifact(argv[0], artifact_buf, sizeof(artifact_buf));
    puts(rf_banner);
    rf_touch_terminal_decoys();
    if (argc < 2 || rf_streq(argv[1], "--help") || rf_streq(argv[1], "help")) {{
        rf_help(argv[0]);
        return argc < 2 ? 1 : 0;
    }}
    if (rf_streq(argv[1], "info")) {{
        puts("local artifact interface: format and validation tables are external");
        return 0;
    }}
    if (rf_streq(argv[1], "verify") || rf_streq(argv[1], "unlock")) {{
        if (argc < 3) {{ puts("missing candidate"); return 1; }}
        if ({validator_name}(artifact_path, argv[2])) {{
            puts({c_string(recipe.success_message)});
            return 0;
        }}
        puts({c_string(recipe.failure_message)});
        return 1;
    }}
    if (rf_streq(argv[1], "check") || rf_streq(argv[1], "inspect") || rf_streq(argv[1], "scan") || rf_streq(argv[1], "run")) {{
        const char *path = argc >= 3 ? argv[2] : artifact_path;
        if ({check_name}(path)) {{
            puts("artifact accepted");
            return 0;
        }}
        puts("artifact rejected");
        return 1;
    }}
{extra_commands}
    puts("unknown command");
    rf_help(argv[0]);
    return 1;
}}
"""


def _firmware_source(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _source_preamble(recipe) + f"""
static int rf_check_firmware_file(const char *path) {{
    size_t len = 0;
    unsigned char *blob = rf_read_file(path, 4096u, &len);
    int ok = blob && len == 7u + (size_t){n}u * 5u && memcmp(blob, "RFFW1", 5u) == 0 && blob[5] == {n}u;
    free(blob);
    return ok;
}}

static int rf_validate_candidate(const char *path, const char *candidate) {{
    size_t len = 0;
    unsigned char *blob;
    unsigned int key;
    const unsigned char *perm;
    const unsigned char *xors;
    const unsigned char *adds;
    const unsigned char *rots;
    const unsigned char *targets;
    if (strlen(candidate) != {n}u) return 0;
    blob = rf_read_file(path, 4096u, &len);
    if (!blob) return 0;
    if (len != 7u + (size_t){n}u * 5u || memcmp(blob, "RFFW1", 5u) != 0 || blob[5] != {n}u) {{ free(blob); return 0; }}
    key = blob[6];
    perm = blob + 7u;
    xors = perm + {n}u;
    adds = xors + {n}u;
    rots = adds + {n}u;
    targets = rots + {n}u;
    for (size_t i = 0; i < {n}u; i++) {{
        unsigned int pos = perm[i];
        unsigned int v;
        unsigned int expected;
        if (pos >= {n}u) {{ free(blob); return 0; }}
        v = rf_rotl8(((((unsigned char)candidate[pos]) ^ xors[i]) + adds[i]) & 0xFFu, rots[i]);
        expected = targets[i] ^ ((key + (unsigned int)i * 17u) & 0xFFu);
        if ((v & 0xFFu) != expected) {{ free(blob); return 0; }}
    }}
    free(blob);
    return 1;
}}
""" + _main_source(
        recipe,
        "rf_validate_candidate",
        "rf_check_firmware_file",
        "",
        '    puts("commands: info | verify <candidate> | check <file> | inspect <file>");\n',
    )


def _license_source(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _source_preamble(recipe) + f"""
static int rf_parse_license(const unsigned char *blob, size_t len, const unsigned char **ops, unsigned int *op_count, unsigned int *key, uint32_t *initial, const unsigned char **code, unsigned int *code_len) {{
    if (len < 12u || memcmp(blob, "RFLIC1", 6u) != 0 || blob[6] != {n}u) return 0;
    *op_count = blob[7];
    *key = blob[8];
    *initial = rf_rd32(blob + 9u);
    if (*op_count < 12u || *op_count > 18u) return 0;
    if (13u + *op_count + 2u > len) return 0;
    *ops = blob + 13u;
    *code_len = rf_rd16(blob + 13u + *op_count);
    *code = blob + 13u + *op_count + 2u;
    return (size_t)(*code - blob) + *code_len <= len;
}}

static int rf_check_license_file(const char *path) {{
    size_t len = 0;
    unsigned char *blob = rf_read_file(path, 8192u, &len);
    const unsigned char *ops = NULL;
    const unsigned char *code = NULL;
    unsigned int op_count = 0, key = 0, code_len = 0;
    uint32_t initial = 0;
    int ok = blob && rf_parse_license(blob, len, &ops, &op_count, &key, &initial, &code, &code_len);
    free(blob);
    return ok;
}}

static unsigned int rf_vm_byte(const unsigned char *code, unsigned int key, unsigned int pc) {{
    return (code[pc] ^ ((key + pc * 13u) & 0xFFu)) & 0xFFu;
}}

static int rf_validate_candidate(const char *path, const char *candidate) {{
    size_t len = 0;
    unsigned char *blob;
    const unsigned char *ops;
    const unsigned char *code;
    unsigned int op_count, key, code_len;
    uint32_t initial, state;
    unsigned int pc = 0, acc = 0, current_index = 0, last_mix = 0;
    if (strlen(candidate) != {n}u) return 0;
    blob = rf_read_file(path, 8192u, &len);
    if (!blob) return 0;
    if (!rf_parse_license(blob, len, &ops, &op_count, &key, &initial, &code, &code_len)) {{ free(blob); return 0; }}
    state = initial;
    while (pc < code_len) {{
        unsigned int op = rf_vm_byte(code, key, pc++);
        if (op == ops[0]) {{ current_index = rf_vm_byte(code, key, pc++); if (current_index >= {n}u) {{ free(blob); return 0; }} acc = (unsigned char)candidate[current_index]; }}
        else if (op == ops[1]) acc = (acc ^ rf_vm_byte(code, key, pc++)) & 0xFFu;
        else if (op == ops[2]) acc = (acc + rf_vm_byte(code, key, pc++)) & 0xFFu;
        else if (op == ops[3]) acc = (acc - rf_vm_byte(code, key, pc++)) & 0xFFu;
        else if (op == ops[4]) acc = rf_rotl8(acc, rf_vm_byte(code, key, pc++));
        else if (op == ops[5]) acc = rf_ror8(acc, rf_vm_byte(code, key, pc++));
        else if (op == ops[6]) {{ last_mix = rf_vm_byte(code, key, pc++); acc = (acc ^ last_mix) & 0xFFu; }}
        else if (op == ops[7]) {{ if (acc != rf_vm_byte(code, key, pc++)) {{ free(blob); return 0; }} }}
        else if (op == ops[8]) {{ state = ((state ^ acc) * 16777619u + current_index + last_mix) & 0xFFFFFFFFu; if (pc < code_len) pc++; }}
        else if (op == ops[9]) pc = rf_vm_byte(code, key, pc++);
        else if (op == ops[10]) {{ unsigned int target = rf_vm_byte(code, key, pc++); if (acc != 0u) pc = target; }}
        else if (op == ops[11]) {{
            uint32_t expected;
            if (pc + 4u > code_len) {{ free(blob); return 0; }}
            expected = rf_vm_byte(code, key, pc);
            expected |= rf_vm_byte(code, key, pc + 1u) << 8u;
            expected |= rf_vm_byte(code, key, pc + 2u) << 16u;
            expected |= rf_vm_byte(code, key, pc + 3u) << 24u;
            free(blob);
            return state == expected;
        }}
        else if (op_count > 12u && op == ops[12]) acc ^= 0u;
        else {{ free(blob); return 0; }}
    }}
    free(blob);
    return 0;
}}
""" + _main_source(
        recipe,
        "rf_validate_candidate",
        "rf_check_license_file",
        "",
        '    puts("commands: info | verify <key> | check <file> | unlock <code>");\n',
    )


def _signal_source(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _source_preamble(recipe) + f"""
static int rf_parse_signal(const unsigned char *blob, size_t len, unsigned int *chunk_count, const unsigned char **lengths, const unsigned char **order, const unsigned char **xors, const unsigned char **adds, const unsigned char **rots, const unsigned char **table, const unsigned char **targets, uint32_t *checksum, unsigned int *key, unsigned int *seed) {{
    size_t off;
    if (len < 10u || memcmp(blob, "RFSIG1", 6u) != 0 || blob[6] != {n}u) return 0;
    *key = blob[7];
    *chunk_count = blob[8];
    *seed = blob[9];
    off = 10u;
    if (*chunk_count == 0u || *chunk_count > {n}u || off + (*chunk_count * 2u) + ((size_t){n}u * 4u) + 256u + 4u > len) return 0;
    *lengths = blob + off; off += *chunk_count;
    *order = blob + off; off += *chunk_count;
    *xors = blob + off; off += {n}u;
    *adds = blob + off; off += {n}u;
    *rots = blob + off; off += {n}u;
    *table = blob + off; off += 256u;
    *targets = blob + off; off += {n}u;
    *checksum = rf_rd32(blob + off);
    return off + 4u <= len;
}}

static int rf_check_signal_file(const char *path) {{
    size_t len = 0;
    unsigned char *blob = rf_read_file(path, 8192u, &len);
    unsigned int cc = 0, key = 0, seed = 0;
    const unsigned char *a = NULL, *b = NULL, *c = NULL, *d = NULL, *e = NULL, *f = NULL, *g = NULL, *h = NULL;
    uint32_t checksum = 0;
    int ok = blob && rf_parse_signal(blob, len, &cc, &a, &b, &c, &d, &e, &f, &g, &checksum, &key, &seed);
    free(blob);
    return ok;
}}

static int rf_validate_candidate(const char *path, const char *candidate) {{
    size_t len = 0;
    unsigned char *blob;
    unsigned int chunk_count, key, seed;
    const unsigned char *lengths, *order, *xors, *adds, *rots, *table_enc, *targets;
    unsigned char table[256];
    unsigned char transformed[{n}];
    unsigned int positions[{n}];
    uint32_t checksum;
    size_t pos_count = 0;
    size_t starts[{n}];
    size_t cursor = 0;
    if (strlen(candidate) != {n}u) return 0;
    blob = rf_read_file(path, 8192u, &len);
    if (!blob) return 0;
    if (!rf_parse_signal(blob, len, &chunk_count, &lengths, &order, &xors, &adds, &rots, &table_enc, &targets, &checksum, &key, &seed)) {{ free(blob); return 0; }}
    for (unsigned int i = 0; i < 256u; i++) table[i] = table_enc[i] ^ ((key + i * 3u) & 0xFFu);
    for (unsigned int i = 0; i < chunk_count; i++) {{ starts[i] = cursor; cursor += lengths[i]; }}
    if (cursor != {n}u) {{ free(blob); return 0; }}
    for (unsigned int oi = 0; oi < chunk_count; oi++) {{
        unsigned int ci = order[oi];
        if (ci >= chunk_count) {{ free(blob); return 0; }}
        for (unsigned int j = 0; j < lengths[ci]; j++) positions[pos_count++] = (unsigned int)starts[ci] + j;
    }}
    if (pos_count != {n}u) {{ free(blob); return 0; }}
    for (size_t i = 0; i < {n}u; i++) {{
        unsigned int v = rf_rotl8(((((unsigned char)candidate[positions[i]]) ^ xors[i]) + adds[i]) & 0xFFu, rots[i]);
        v = table[v & 0xFFu];
        transformed[i] = (unsigned char)v;
        if ((v ^ ((key + (unsigned int)i * 11u) & 0xFFu)) != targets[i]) {{ free(blob); return 0; }}
    }}
    if (rf_roll_hash_bytes(transformed, {n}u, 0xA5A50000u | seed) != checksum) {{ free(blob); return 0; }}
    free(blob);
    return 1;
}}
""" + _main_source(
        recipe,
        "rf_validate_candidate",
        "rf_check_signal_file",
        "",
        '    puts("commands: scan <file> | verify <candidate>");\n',
    )


def _constraints_source(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _source_preamble(recipe) + f"""
static int rf_check_record(const unsigned char *candidate, const uint32_t *v, unsigned int type) {{
    if (type == 1u) return candidate[v[0]] + candidate[v[1]] == v[2];
    if (type == 2u) return (candidate[v[0]] ^ candidate[v[1]]) == v[2];
    if (type == 3u) return (rf_rotl8(candidate[v[0]], v[2]) ^ candidate[v[1]]) == v[3];
    if (type == 4u) return ((candidate[v[0]] * v[1]) + v[2]) % v[3] == v[4];
    if (type == 5u) return (candidate[v[0]] * 3u + candidate[v[1]] * 5u + candidate[v[2]] * 7u) % 257u == v[3];
    if (type == 6u) return rf_roll_hash_bytes(candidate + v[0], v[1], 0xC0DE0000u | v[2]) == v[3];
    return 0;
}}

static int rf_walk_constraints(const unsigned char *blob, size_t len, const char *candidate, int validate_candidate) {{
    unsigned int key, count;
    size_t off = 8u;
    if (len < 8u || memcmp(blob, "RFCON1", 6u) != 0 || blob[6] != {n}u) return 0;
    key = blob[7];
    count = rf_rd16(blob + 8u);
    off = 10u;
    for (unsigned int rec = 0; rec < count; rec++) {{
        unsigned int type;
        unsigned int argc;
        uint32_t values[8] = {{0}};
        if (off + 2u > len) return 0;
        type = blob[off] ^ ((key + (unsigned int)(off - 10u) * 5u) & 0xFFu);
        argc = blob[off + 1u] ^ ((key + (unsigned int)(off + 1u - 10u) * 5u) & 0xFFu);
        off += 2u;
        if (argc > 8u || off + argc * 4u > len) return 0;
        for (unsigned int i = 0; i < argc; i++) {{
            unsigned char tmp[4];
            for (unsigned int j = 0; j < 4u; j++) tmp[j] = blob[off + i * 4u + j] ^ ((key + (unsigned int)(off + i * 4u + j - 10u) * 5u) & 0xFFu);
            values[i] = rf_rd32(tmp);
            if ((i < 3u || type == 4u) && values[i] >= 100000u) return 0;
        }}
        off += argc * 4u;
        if (validate_candidate && !rf_check_record((const unsigned char *)candidate, values, type)) return 0;
    }}
    return off <= len;
}}

static int rf_check_constraints_file(const char *path) {{
    size_t len = 0;
    unsigned char *blob = rf_read_file(path, 32768u, &len);
    int ok = blob && rf_walk_constraints(blob, len, "", 0);
    free(blob);
    return ok;
}}

static int rf_validate_candidate(const char *path, const char *candidate) {{
    size_t len = 0;
    unsigned char *blob;
    int ok;
    if (strlen(candidate) != {n}u) return 0;
    blob = rf_read_file(path, 32768u, &len);
    if (!blob) return 0;
    ok = rf_walk_constraints(blob, len, candidate, 1);
    free(blob);
    return ok;
}}
""" + _main_source(
        recipe,
        "rf_validate_candidate",
        "rf_check_constraints_file",
        "",
        '    puts("commands: verify <candidate> | check <file> | inspect <file>");\n',
    )


def _hybrid_source(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _source_preamble(recipe) + f"""
static int rf_parse_hybrid(const unsigned char *blob, size_t len) {{
    return len > 32u && memcmp(blob, "RFHYB1", 6u) == 0 && blob[6] == {n}u;
}}

static int rf_hybrid_vm(const unsigned char *blob, size_t len, const char *candidate, size_t *out_off) {{
    unsigned int vm_key, op_count, code_len, pc = 0, acc = 0, idx = 0, mix = 0;
    const unsigned char *ops;
    const unsigned char *code;
    uint32_t state;
    size_t off;
    if (!rf_parse_hybrid(blob, len)) return 0;
    vm_key = blob[7];
    op_count = blob[9];
    state = rf_rd32(blob + 10u);
    ops = blob + 14u;
    off = 14u + op_count;
    if (op_count != 18u || off + 2u > len) return 0;
    code_len = rf_rd16(blob + off); off += 2u;
    code = blob + off; off += code_len;
    if (off > len) return 0;
    while (pc < code_len) {{
        unsigned int op = code[pc] ^ ((vm_key + pc * 7u) & 0xFFu); pc++;
        if (op == ops[0]) {{ idx = code[pc] ^ ((vm_key + pc * 7u) & 0xFFu); pc++; if (idx >= {n}u) return 0; acc = (unsigned char)candidate[idx]; }}
        else if (op == ops[1]) {{ acc = (acc ^ (code[pc] ^ ((vm_key + pc * 7u) & 0xFFu))) & 0xFFu; pc++; }}
        else if (op == ops[2]) {{ acc = (acc + (code[pc] ^ ((vm_key + pc * 7u) & 0xFFu))) & 0xFFu; pc++; }}
        else if (op == ops[3]) {{ acc = rf_rotl8(acc, code[pc] ^ ((vm_key + pc * 7u) & 0xFFu)); pc++; }}
        else if (op == ops[4]) {{ mix = code[pc] ^ ((vm_key + pc * 7u) & 0xFFu); acc = (acc ^ mix) & 0xFFu; pc++; }}
        else if (op == ops[5]) {{ unsigned int expected = code[pc] ^ ((vm_key + pc * 7u) & 0xFFu); pc++; if (acc != expected) return 0; }}
        else if (op == ops[6]) {{ state = ((state ^ acc) * 16777619u + idx + mix) & 0xFFFFFFFFu; if (pc < code_len) pc++; }}
        else if (op == ops[7]) {{
            uint32_t expected;
            expected = code[pc] ^ ((vm_key + pc * 7u) & 0xFFu);
            expected |= (code[pc + 1u] ^ ((vm_key + (pc + 1u) * 7u) & 0xFFu)) << 8u;
            expected |= (code[pc + 2u] ^ ((vm_key + (pc + 2u) * 7u) & 0xFFu)) << 16u;
            expected |= (code[pc + 3u] ^ ((vm_key + (pc + 3u) * 7u) & 0xFFu)) << 24u;
            *out_off = off;
            return state == expected;
        }}
        else if (op == ops[8]) {{ if (pc < code_len) pc++; }}
        else return 0;
    }}
    return 0;
}}

static int rf_hybrid_constraints(const unsigned char *blob, size_t len, const char *candidate, size_t *off) {{
    unsigned int count;
    if (*off + 2u > len) return 0;
    count = rf_rd16(blob + *off);
    *off += 2u;
    if (*off + (size_t)count * 16u > len) return 0;
    for (unsigned int i = 0; i < count; i++) {{
        uint32_t idx = rf_rd32(blob + *off); *off += 4u;
        uint32_t mult = rf_rd32(blob + *off); *off += 4u;
        uint32_t add = rf_rd32(blob + *off); *off += 4u;
        uint32_t target = rf_rd32(blob + *off); *off += 4u;
        if (idx >= {n}u) return 0;
        if ((((unsigned char)candidate[idx] * mult) + add) % 257u != target) return 0;
    }}
    return 1;
}}

static int rf_hybrid_pipeline(const unsigned char *blob, size_t len, const char *candidate, size_t off) {{
    unsigned int pipe_key = blob[8];
    const unsigned char *xors;
    const unsigned char *adds;
    const unsigned char *rots;
    const unsigned char *targets;
    unsigned char values[{n}];
    uint32_t expected_hash;
    if (off + (size_t){n}u * 4u + 4u > len) return 0;
    xors = blob + off; off += {n}u;
    adds = blob + off; off += {n}u;
    rots = blob + off; off += {n}u;
    targets = blob + off; off += {n}u;
    expected_hash = rf_rd32(blob + off);
    for (size_t i = 0; i < {n}u; i++) {{
        unsigned int v = rf_rotl8(((((unsigned char)candidate[i]) ^ xors[i]) + adds[i]) & 0xFFu, rots[i]);
        values[i] = (unsigned char)v;
        if ((v ^ ((pipe_key + (unsigned int)i * 19u) & 0xFFu)) != targets[i]) return 0;
    }}
    return rf_roll_hash_bytes(values, {n}u, 0xF17A1000u | pipe_key) == expected_hash;
}}

static int rf_check_hybrid_file(const char *path) {{
    size_t len = 0;
    unsigned char *blob = rf_read_file(path, 65536u, &len);
    int ok = blob && rf_parse_hybrid(blob, len);
    free(blob);
    return ok;
}}

static int rf_validate_candidate(const char *path, const char *candidate) {{
    size_t len = 0, off = 0;
    unsigned char *blob;
    int ok;
    if (strlen(candidate) != {n}u) return 0;
    blob = rf_read_file(path, 65536u, &len);
    if (!blob) return 0;
    ok = rf_hybrid_vm(blob, len, candidate, &off) && rf_hybrid_constraints(blob, len, candidate, &off) && rf_hybrid_pipeline(blob, len, candidate, off);
    free(blob);
    return ok;
}}
""" + _main_source(
        recipe,
        "rf_validate_candidate",
        "rf_check_hybrid_file",
        "",
        '    puts("commands: info | verify <candidate> | check <file> | run <file>");\n',
    )


def _solver_header(recipe: ChallengeRecipe) -> str:
    artifact = recipe.constants["artifact_name"]
    return f"""#!/usr/bin/env python3
# Created by {CREATED_BY}
from __future__ import annotations

from pathlib import Path


def artifact_path(name={artifact!r}):
    here = Path(__file__).resolve().parents[1]
    return here / name


def rol8(value, amount):
    amount &= 7
    return ((value << amount) | (value >> (8 - amount))) & 0xff


def ror8(value, amount):
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xff


def rd16(data, off):
    return data[off] | (data[off + 1] << 8)


def rd32(data, off):
    return data[off] | (data[off + 1] << 8) | (data[off + 2] << 16) | (data[off + 3] << 24)


def roll_hash(values, seed):
    h = seed & 0xffffffff
    for value in values:
        h = ((h ^ value) * 16777619 + 0x9E3779B9) & 0xffffffff
        h ^= h >> 13
    return h & 0xffffffff


"""


def _firmware_solver(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _solver_header(recipe) + f"""blob = artifact_path().read_bytes()
if blob[:5] != b"RFFW1" or blob[5] != {n}:
    raise SystemExit("unexpected firmware blob")
key = blob[6]
off = 7
perm = list(blob[off:off + {n}]); off += {n}
xors = list(blob[off:off + {n}]); off += {n}
adds = list(blob[off:off + {n}]); off += {n}
rots = list(blob[off:off + {n}]); off += {n}
targets = list(blob[off:off + {n}])
out = ["?"] * {n}
for i, pos in enumerate(perm):
    expected = targets[i] ^ ((key + i * 17) & 0xff)
    for candidate in range(32, 127):
        if rol8(((candidate ^ xors[i]) + adds[i]) & 0xff, rots[i]) == expected:
            out[pos] = chr(candidate)
            break
    else:
        raise SystemExit(f"no byte for table row {{i}}")
print("".join(out))
"""


def _license_solver(recipe: ChallengeRecipe) -> str:
    return _solver_header(recipe) + """blob = artifact_path().read_bytes()
if blob[:6] != b"RFLIC1":
    raise SystemExit("unexpected license capsule")
n = blob[6]
op_count = blob[7]
key = blob[8]
ops = list(blob[13:13 + op_count])
off = 13 + op_count
code_len = rd16(blob, off); off += 2
encoded = blob[off:off + code_len]

def dec(pc):
    return encoded[pc] ^ ((key + pc * 13) & 0xff)

pc = 0
out = ["?"] * n
while pc < code_len:
    op = dec(pc); pc += 1
    if op == ops[0]:
        idx = dec(pc); pc += 1
        steps = []
    elif op == ops[1]:
        steps.append(("xor", dec(pc))); pc += 1
    elif op == ops[2]:
        steps.append(("add", dec(pc))); pc += 1
    elif op == ops[3]:
        steps.append(("sub", dec(pc))); pc += 1
    elif op == ops[4]:
        steps.append(("rol", dec(pc))); pc += 1
    elif op == ops[5]:
        steps.append(("ror", dec(pc))); pc += 1
    elif op == ops[6]:
        steps.append(("mix", dec(pc))); pc += 1
    elif op == ops[7]:
        expected = dec(pc); pc += 1
        for candidate in range(32, 127):
            value = candidate
            for name, arg in steps:
                if name == "xor":
                    value ^= arg
                elif name == "add":
                    value = (value + arg) & 0xff
                elif name == "sub":
                    value = (value - arg) & 0xff
                elif name == "rol":
                    value = rol8(value, arg)
                elif name == "ror":
                    value = ror8(value, arg)
                elif name == "mix":
                    value ^= arg
            if value == expected:
                out[idx] = chr(candidate)
                break
        else:
            raise SystemExit(f"no candidate for byte {idx}")
    elif op == ops[8]:
        pc += 1
    elif op == ops[11]:
        break
    else:
        if op_count > 12 and op == ops[12]:
            pass
        else:
            break
print("".join(out))
"""


def _signal_solver(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _solver_header(recipe) + f"""blob = artifact_path().read_bytes()
if blob[:6] != b"RFSIG1" or blob[6] != {n}:
    raise SystemExit("unexpected signal data")
key = blob[7]
chunk_count = blob[8]
seed = blob[9]
off = 10
lengths = list(blob[off:off + chunk_count]); off += chunk_count
order = list(blob[off:off + chunk_count]); off += chunk_count
xors = list(blob[off:off + {n}]); off += {n}
adds = list(blob[off:off + {n}]); off += {n}
rots = list(blob[off:off + {n}]); off += {n}
table = [blob[off + i] ^ ((key + i * 3) & 0xff) for i in range(256)]; off += 256
targets = list(blob[off:off + {n}])
starts = []
cursor = 0
for length in lengths:
    starts.append(cursor)
    cursor += length
positions = []
for chunk_index in order:
    positions.extend(range(starts[chunk_index], starts[chunk_index] + lengths[chunk_index]))
out = ["?"] * {n}
for i, pos in enumerate(positions):
    expected = targets[i] ^ ((key + i * 11) & 0xff)
    for candidate in range(32, 127):
        value = rol8(((candidate ^ xors[i]) + adds[i]) & 0xff, rots[i])
        if table[value] == expected:
            out[pos] = chr(candidate)
            break
    else:
        raise SystemExit(f"no signal byte at row {{i}}")
print("".join(out))
"""


def _constraints_solver(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _solver_header(recipe) + f"""blob = artifact_path().read_bytes()
if blob[:6] != b"RFCON1" or blob[6] != {n}:
    raise SystemExit("unexpected constraints pack")
key = blob[7]
count = rd16(blob, 8)
off = 10
records = []
for _ in range(count):
    typ = blob[off] ^ ((key + (off - 10) * 5) & 0xff)
    argc = blob[off + 1] ^ ((key + (off + 1 - 10) * 5) & 0xff)
    off += 2
    values = []
    for _ in range(argc):
        raw = bytes(blob[off + j] ^ ((key + (off + j - 10) * 5) & 0xff) for j in range(4))
        values.append(rd32(raw, 0))
        off += 4
    records.append((typ, values))

try:
    import z3  # type: ignore
except Exception:
    z3 = None

out = [None] * {n}
if z3 is not None:
    chars = [z3.BitVec(f"c{{i}}", 8) for i in range({n})]
    solver = z3.Solver()
    for c in chars:
        solver.add(c >= 32, c <= 126)
    for typ, values in records:
        if typ == 1:
            solver.add(z3.ZeroExt(8, chars[values[0]]) + z3.ZeroExt(8, chars[values[1]]) == values[2])
        elif typ == 2:
            solver.add(chars[values[0]] ^ chars[values[1]] == values[2])
        elif typ == 4:
            solver.add(((z3.ZeroExt(8, chars[values[0]]) * values[1]) + values[2]) % values[3] == values[4])
    if solver.check() == z3.sat:
        model = solver.model()
        out = [model.eval(c).as_long() for c in chars]

if any(value is None for value in out):
    for typ, values in records:
        if typ == 4:
            idx, mult, add, mod, target = values
            if out[idx] is None:
                for candidate in range(32, 127):
                    if ((candidate * mult) + add) % mod == target:
                        out[idx] = candidate
                        break
    if any(value is None for value in out):
        raise SystemExit("pure solver could not recover every byte")
print("".join(chr(int(value)) for value in out))
"""


def _hybrid_solver(recipe: ChallengeRecipe) -> str:
    n = recipe.constants["flag_length"]
    return _solver_header(recipe) + f"""blob = artifact_path().read_bytes()
if blob[:6] != b"RFHYB1" or blob[6] != {n}:
    raise SystemExit("unexpected hybrid capsule")
vm_key = blob[7]
op_count = blob[9]
ops = list(blob[14:14 + op_count])
off = 14 + op_count
code_len = rd16(blob, off); off += 2
encoded = blob[off:off + code_len]; off += code_len

def dec(pc):
    return encoded[pc] ^ ((vm_key + pc * 7) & 0xff)

pc = 0
out = ["?"] * {n}
while pc < code_len:
    op = dec(pc); pc += 1
    if op == ops[0]:
        idx = dec(pc); pc += 1
        steps = []
    elif op == ops[1]:
        steps.append(("xor", dec(pc))); pc += 1
    elif op == ops[2]:
        steps.append(("add", dec(pc))); pc += 1
    elif op == ops[3]:
        steps.append(("rol", dec(pc))); pc += 1
    elif op == ops[4]:
        steps.append(("mix", dec(pc))); pc += 1
    elif op == ops[5]:
        expected = dec(pc); pc += 1
        for candidate in range(32, 127):
            value = candidate
            for name, arg in steps:
                if name == "xor":
                    value ^= arg
                elif name == "add":
                    value = (value + arg) & 0xff
                elif name == "rol":
                    value = rol8(value, arg)
                elif name == "mix":
                    value ^= arg
            if value == expected:
                out[idx] = chr(candidate)
                break
        else:
            raise SystemExit(f"no VM byte for {{idx}}")
    elif op == ops[6]:
        pc += 1
    elif op == ops[7]:
        break
    elif op == ops[8]:
        if pc < code_len:
            pc += 1
    else:
        break
if any(ch == "?" for ch in out):
    raise SystemExit("VM reconstruction incomplete")
print("".join(out))
"""


def _terminal_writeup(recipe: ChallengeRecipe) -> str:
    return f"""# Writeup

Created by {CREATED_BY}

This training bundle uses `{recipe.template_family}` with `{recipe.profile}` profile and `{recipe.style}` style.

Intended reversing path:

1. Run the binary with `--help` and identify the local artifact files.
2. Inspect the binary and artifacts with terminal reversing tools.
3. Recover the file format, encoded tables, bytecode, constraints, or pipeline parameters.
4. Rebuild the validator in Python and submit the recovered candidate to `verify`.

The included solver parses the local artifact and reconstructs the candidate from encoded data rather than printing a literal answer.
"""
