"""Template preparation and source rendering for RevForge v0.2.0."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random
from typing import Any

from ..flags import render_flag
from ..recipes import ChallengeRecipe, TEMPLATES_BY_DIFFICULTY
from ..terminal import is_terminal_family, prepare_terminal_recipe, render_terminal
from ..utils import BANNER, CREATED_BY, c_array, c_string


@dataclass(frozen=True)
class TemplateRender:
    cli_source: str
    android_source: str
    solution: str
    writeup: str
    artifacts: dict[str, bytes] | None = None


SUCCESS_MESSAGES = [
    "Accepted. Validation path reached.",
    "Correct input. Training objective complete.",
    "State matched. Challenge solved.",
    "Good signal. The checker accepted the candidate.",
]

FAILURE_MESSAGES = [
    "Rejected. Keep reversing.",
    "No match.",
    "State mismatch.",
    "Incorrect candidate.",
]

STORIES = [
    "A local validation routine checks one candidate string without side effects.",
    "The binary contains a generated validation algorithm for reverse engineering practice.",
    "The challenge is a safe crackme-style exercise with randomized constants.",
    "The intended path is static analysis plus a small reconstruction script.",
]

FAKE_STRINGS = [
    "debug=false",
    "training_build_only",
    "debug route disabled",
    "local validator",
    "invalid signal block",
    "analysis note: no network",
    "checksum mismatch",
    "firmware gate closed",
    "state transition rejected",
    "calibration failed",
    "trace segment rejected",
    "license window expired",
]


def implemented_templates() -> dict[str, tuple[str, ...]]:
    return TEMPLATES_BY_DIFFICULTY


def prepare_recipe(recipe: ChallengeRecipe, rng: Random) -> ChallengeRecipe:
    recipe.success_message = rng.choice(SUCCESS_MESSAGES)
    recipe.failure_message = rng.choice(FAILURE_MESSAGES)
    recipe.story = rng.choice(STORIES)
    recipe.fake_strings = rng.sample(FAKE_STRINGS, k=rng.randint(2, 4))
    recipe.fake_flags = _fake_flags(recipe, rng) if recipe.fake_flags_enabled else []
    recipe.compiler_flags = ["-std=c11", "-O2", "-Wall", "-Wextra"]
    if recipe.difficulty in {"hard", "super-hard"}:
        recipe.compiler_flags.append("-s")

    flag_bytes = list(recipe.flag.encode("utf-8"))
    recipe.constants["flag_length"] = len(flag_bytes)

    template = recipe.template_family
    if is_terminal_family(template):
        return prepare_terminal_recipe(recipe, rng, flag_bytes)
    if template == "baby_strings":
        _prep_baby_strings(recipe)
    elif template == "baby_reverse":
        _prep_baby_reverse(recipe)
    elif template == "baby_caesar":
        _prep_baby_caesar(recipe, rng, flag_bytes)
    elif template == "easy_xor_chunks":
        _prep_easy_xor_chunks(recipe, rng, flag_bytes)
    elif template == "easy_arithmetic_check":
        _prep_easy_arithmetic_check(recipe, rng, flag_bytes)
    elif template == "easy_permutation":
        _prep_easy_permutation(recipe, rng, flag_bytes)
    elif template == "medium_multi_stage":
        _prep_medium_multi_stage(recipe, rng, flag_bytes)
    elif template == "medium_crc_gate":
        _prep_medium_crc_gate(recipe, rng, flag_bytes)
    elif template == "medium_table_vm_lite":
        _prep_medium_table_vm_lite(recipe, rng, flag_bytes)
    elif template == "hard_state_machine":
        _prep_hard_state_machine(recipe, rng, flag_bytes)
    elif template == "hard_mixed_constraints":
        _prep_hard_mixed_constraints(recipe, rng, flag_bytes)
    elif template == "hard_encoded_table":
        _prep_hard_encoded_table(recipe, rng, flag_bytes)
    elif template == "superhard_toy_vm_real":
        _prep_superhard_toy_vm_real(recipe, rng, flag_bytes)
    elif template == "superhard_symbolic_constraints":
        _prep_superhard_symbolic_constraints(recipe, rng, flag_bytes)
    elif template == "superhard_state_vm_combo":
        _prep_superhard_state_vm_combo(recipe, rng, flag_bytes)
    else:
        raise ValueError(f"template is not implemented: {template}")
    return recipe


def render(recipe: ChallengeRecipe) -> TemplateRender:
    if is_terminal_family(recipe.template_family):
        terminal = render_terminal(recipe)
        return TemplateRender(
            cli_source=terminal.source,
            android_source=terminal.source,
            solution=terminal.solution,
            writeup=terminal.writeup,
            artifacts=terminal.artifacts,
        )
    checker = _checker_code(recipe)
    cli_source = _wrap_cli(recipe, checker)
    android_source = _wrap_android(recipe, checker)
    return TemplateRender(
        cli_source=cli_source,
        android_source=android_source,
        solution=_solution_script(recipe),
        writeup=_writeup(recipe),
        artifacts={},
    )


def _fake_flags(recipe: ChallengeRecipe, rng: Random) -> list[str]:
    flags: list[str] = []
    count = max(0, recipe.fake_flag_count)
    while len(flags) < count:
        candidate = _fake_flag_value(recipe, rng, len(flags))
        if candidate != recipe.flag and candidate not in flags:
            flags.append(candidate)
    return flags


def _fake_flag_value(recipe: ChallengeRecipe, rng: Random, index: int) -> str:
    value = f"decoy_{rng.getrandbits(24):06x}"
    if recipe.fake_flag_style == "generic":
        return f"flag{{{value}}}"
    if recipe.fake_flag_style == "ctf":
        return f"CTF{{{value}}}"
    if recipe.fake_flag_style == "mixed":
        formats = (
            recipe.flag_format,
            "flag{{{value}}}",
            "CTF{{{value}}}",
            "revforge{{{value}}}",
        )
        return render_flag(formats[index % len(formats)], value)
    return render_flag(recipe.flag_format, value)


def _prep_baby_strings(recipe: ChallengeRecipe) -> None:
    recipe.encoding_chain = ["plaintext string"]
    recipe.checker_type = "visible-string-compare"
    recipe.constants["expected"] = recipe.flag
    recipe.transformations = ["none"]
    recipe.operations = ["strlen", "strcmp"]
    recipe.checker_logic = "The expected input is intentionally visible for absolute beginners."


def _prep_baby_reverse(recipe: ChallengeRecipe) -> None:
    recipe.encoding_chain = ["reverse"]
    recipe.checker_type = "reverse-before-compare"
    recipe.constants["reversed_flag"] = recipe.flag[::-1]
    recipe.transformations = ["reverse input"]
    recipe.operations = ["strlen", "indexed compare"]
    recipe.checker_logic = "Input is compared against a reversed constant."


def _prep_baby_caesar(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    shift = rng.randint(1, 25)
    recipe.encoding_chain = ["caesar byte shift"]
    recipe.checker_type = "caesar-array"
    recipe.constants["shift"] = shift
    recipe.constants["encoded"] = [((b + shift) & 0xFF) for b in flag_bytes]
    recipe.transformations = [f"byte + {shift}"]
    recipe.operations = ["strlen", "byte addition"]
    recipe.checker_logic = "Each input byte is shifted and compared with an encoded array."


def _prep_easy_xor_chunks(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    chunks = _split_bytes(flag_bytes, rng, 3, 6)
    keys = [rng.randint(1, 255) for _ in chunks]
    encoded = [[b ^ keys[i] for b in chunk] for i, chunk in enumerate(chunks)]
    recipe.encoding_chain = ["chunk", "xor per chunk"]
    recipe.checker_type = "xor-chunk-validator"
    recipe.constants.update({"chunk_lengths": [len(c) for c in chunks], "keys": keys, "encoded_chunks": encoded})
    recipe.transformations = ["split input", "xor each chunk with a different key"]
    recipe.operations = ["chunk loop", "xor", "array compare"]
    recipe.checker_logic = "The flag is split and each chunk is validated with a different XOR key."


def _prep_easy_arithmetic_check(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    muls, adds, targets = _byte_mod_constraints(flag_bytes, rng)
    recipe.encoding_chain = ["modular arithmetic"]
    recipe.checker_type = "per-character-arithmetic"
    recipe.constants.update({"modulus": 257, "muls": muls, "adds": adds, "targets": targets})
    recipe.transformations = ["input[i] * a + b mod 257"]
    recipe.operations = ["integer arithmetic", "array compare"]
    recipe.checker_logic = "Each character is validated by an independent modular arithmetic equation."


def _prep_easy_permutation(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    permutation = list(range(len(flag_bytes)))
    rng.shuffle(permutation)
    key = rng.randint(1, 255)
    encoded = [flag_bytes[index] ^ ((key + i * 17) & 0xFF) for i, index in enumerate(permutation)]
    recipe.encoding_chain = ["permutation", "xor"]
    recipe.checker_type = "permuted-array"
    recipe.constants.update({"permutation": permutation, "key": key, "encoded": encoded})
    recipe.transformations = ["permute input positions", "xor with index-derived key"]
    recipe.operations = ["permuted index", "xor"]
    recipe.checker_logic = "Input characters are checked in a shuffled order against encoded bytes."


def _prep_medium_multi_stage(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    muls, adds, targets = _byte_mod_constraints(flag_bytes, rng)
    chunks = _split_bytes(flag_bytes, rng, 4, 6)
    chunk_seeds = [0x9E3779B1 ^ rng.randint(0, 0xFFFF) for _ in chunks]
    chunk_hashes = [_rolling_hash(chunk, chunk_seeds[i]) for i, chunk in enumerate(chunks)]
    chunk_lengths = [len(chunk) for chunk in chunks]
    lookup_key = rng.randint(1, 255)
    permutation = list(range(len(flag_bytes)))
    rng.shuffle(permutation)
    lookup = [((flag_bytes[index] ^ lookup_key) + (i * 11)) & 0xFF for i, index in enumerate(permutation)]
    prefix_len = min(3, len(flag_bytes))
    suffix_len = min(1, len(flag_bytes))
    recipe.encoding_chain = ["length guard", "arithmetic", "rolling hash", "encoded lookup"]
    recipe.checker_type = "multi-stage-validator"
    recipe.constants.update(
        {
            "prefix_values": flag_bytes[:prefix_len],
            "suffix_values": flag_bytes[-suffix_len:],
            "modulus": 257,
            "muls": muls,
            "adds": adds,
            "targets": targets,
            "chunk_lengths": chunk_lengths,
            "chunk_seeds": chunk_seeds,
            "chunk_hashes": chunk_hashes,
            "lookup_key": lookup_key,
            "permutation": permutation,
            "lookup": lookup,
        }
    )
    recipe.stages = [
        {"name": "length-prefix-suffix"},
        {"name": "arithmetic constraints"},
        {"name": "rolling chunk hashes"},
        {"name": "encoded lookup table"},
    ]
    recipe.transformations = ["numeric prefix/suffix guard", "modular equations", "chunk hash", "permuted lookup"]
    recipe.operations = ["strlen", "mod 257", "rolling hash", "permuted array"]
    recipe.checker_logic = "Four staged checks must agree before the candidate is accepted."


def _prep_medium_crc_gate(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    chunks = _split_bytes(flag_bytes, rng, 4, 7)
    seeds = [rng.randint(0, 0xFFFFFFFF) for _ in chunks]
    crc_targets = [_custom_crc(chunk, seeds[i]) for i, chunk in enumerate(chunks)]
    xors = [rng.randint(1, 255) for _ in flag_bytes]
    adds = [rng.randint(0, 255) for _ in flag_bytes]
    targets = [((b ^ xors[i]) + adds[i] + i) & 0xFF for i, b in enumerate(flag_bytes)]
    decoys = [rng.randint(0, 0xFFFFFFFF) for _ in range(4)]
    recipe.encoding_chain = ["chunk crc", "byte transform", "decoy gates"]
    recipe.checker_type = "crc-gated-validator"
    recipe.constants.update(
        {
            "chunk_lengths": [len(c) for c in chunks],
            "crc_seeds": seeds,
            "crc_targets": crc_targets,
            "xors": xors,
            "adds": adds,
            "targets": targets,
            "decoy_crc_targets": decoys,
        }
    )
    recipe.transformations = ["custom CRC per chunk", "byte xor/add equations"]
    recipe.operations = ["custom crc32-like loop", "decoy checksum branch", "byte transform"]
    recipe.checker_logic = "Chunk checksums and per-byte equations must both match."


def _prep_medium_table_vm_lite(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    opcodes = _opcode_map(rng, ["LOAD", "XOR", "ADD", "ROL", "CMP", "MIX", "HALT"])
    program: list[int] = []
    instructions: list[dict[str, int]] = []
    for i, b in enumerate(flag_bytes):
        xk = rng.randint(1, 255)
        add = rng.randint(0, 255)
        rot = rng.randint(1, 7)
        mix = rng.randint(1, 255)
        expected = ((_rotl8(((b ^ xk) + add) & 0xFF, rot) ^ mix) + i) & 0xFF
        program.extend([opcodes["LOAD"], i, opcodes["XOR"], xk, opcodes["ADD"], add, opcodes["ROL"], rot])
        program.extend([opcodes["MIX"], mix, opcodes["CMP"], expected])
        instructions.append({"index": i, "xor": xk, "add": add, "rot": rot, "mix": mix, "expected": expected})
    program.append(opcodes["HALT"])
    recipe.encoding_chain = ["table vm lite"]
    recipe.checker_type = "lite-bytecode-interpreter"
    recipe.constants.update({"opcodes": opcodes, "program": program, "instructions": instructions})
    recipe.stages = instructions
    recipe.transformations = ["LOAD", "XOR", "ADD", "ROL", "MIX", "CMP"]
    recipe.operations = ["switch interpreter", "bytecode table"]
    recipe.checker_logic = "A compact interpreter transforms each byte before comparison."


def _prep_hard_state_machine(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    state_count = max(48, len(flag_bytes) + 20)
    alphabet_size = 128
    dead_state = state_count - 1
    table = [[dead_state for _ in range(alphabet_size)] for _ in range(state_count)]
    for state in range(state_count - 1):
        for byte in range(32, 127):
            table[state][byte] = rng.randint(0, state_count - 2)
    path = [rng.randint(0, state_count - 2)]
    for _ in flag_bytes:
        nxt = rng.randint(0, state_count - 2)
        path.append(nxt)
    for i, b in enumerate(flag_bytes):
        table[path[i]][b] = path[i + 1]
    keys = [rng.randint(1, 255) for _ in flag_bytes]
    pos_targets = [((b ^ keys[i]) + i * 3) & 0xFF for i, b in enumerate(flag_bytes)]
    recipe.encoding_chain = ["dfa", "position constraints"]
    recipe.checker_type = "generated-state-machine"
    recipe.constants.update(
        {
            "state_count": state_count,
            "alphabet_size": alphabet_size,
            "start_state": path[0],
            "accept_state": path[-1],
            "dead_state": dead_state,
            "transition_table": table,
            "path_states": path,
            "keys": keys,
            "pos_targets": pos_targets,
        }
    )
    recipe.transformations = ["transition table", "per-position encoded constraints"]
    recipe.operations = ["dfa transition", "accept state", "dead states"]
    recipe.checker_logic = "The candidate must walk a generated DFA to the accept state while satisfying position checks."


def _prep_hard_mixed_constraints(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    muls, adds, targets = _byte_mod_constraints(flag_bytes, rng)
    pair_constraints = []
    for i in range(len(flag_bytes) // 2):
        j = len(flag_bytes) - 1 - i
        pair_constraints.append({"i": i, "j": j, "sum": flag_bytes[i] + flag_bytes[j], "xor": flag_bytes[i] ^ flag_bytes[j]})
    for _ in range(max(4, len(flag_bytes) // 3)):
        i, j = rng.sample(range(len(flag_bytes)), 2)
        pair_constraints.append({"i": i, "j": j, "sum": flag_bytes[i] + flag_bytes[j], "xor": flag_bytes[i] ^ flag_bytes[j]})
    recipe.encoding_chain = ["unary modular constraints", "pair constraints"]
    recipe.checker_type = "mixed-symbolic-constraints"
    recipe.constants.update({"modulus": 257, "muls": muls, "adds": adds, "targets": targets, "pairs": pair_constraints})
    recipe.transformations = ["input[i] * a + b mod 257", "pair sum", "pair xor"]
    recipe.operations = ["modular arithmetic", "pair relationships"]
    recipe.checker_logic = "The binary checks per-character and pairwise equations."


def _prep_hard_encoded_table(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    xors = [rng.randint(1, 255) for _ in flag_bytes]
    adds = [rng.randint(0, 255) for _ in flag_bytes]
    rots = [rng.randint(1, 7) for _ in flag_bytes]
    masks = [rng.randint(1, 255) for _ in flag_bytes]
    encoded = []
    for i, b in enumerate(flag_bytes):
        v = b ^ xors[i]
        v = (v + adds[i] + i) & 0xFF
        v = _rotl8(v, rots[i])
        encoded.append(v ^ masks[i])
    recipe.encoding_chain = ["xor", "add", "rotate", "mask"]
    recipe.checker_type = "encoded-table-decoder"
    recipe.constants.update({"xors": xors, "adds": adds, "rots": rots, "masks": masks, "encoded": encoded})
    recipe.transformations = ["small decode functions", "encoded constants only"]
    recipe.operations = ["xor", "add", "rotl", "indirect helper calls"]
    recipe.checker_logic = "Constants are decoded through several small functions before comparison."


def _prep_superhard_toy_vm_real(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    names = ["LOAD_INPUT", "XOR", "ADD", "SUB", "ROL", "ROR", "MIX", "JMP", "JNZ", "CMP", "HALT", "NOP"]
    opcodes = _opcode_map(rng, names)
    program: list[int] = []
    instructions: list[dict[str, int]] = []
    initial_state = rng.randint(0, 0xFFFFFFFF)
    state = initial_state
    for i, b in enumerate(flag_bytes):
        xk = rng.randint(1, 255)
        add = rng.randint(0, 255)
        sub = rng.randint(0, 255)
        rol = rng.randint(1, 7)
        ror = rng.randint(1, 7)
        mix = rng.randint(1, 255)
        v = b
        v ^= xk
        v = (v + add) & 0xFF
        v = (v - sub) & 0xFF
        v = _rotl8(v, rol)
        v = _ror8(v, ror)
        v ^= mix
        state = ((state ^ v) * 16777619 + i + mix) & 0xFFFFFFFF
        program.extend(
            [
                opcodes["LOAD_INPUT"],
                i,
                opcodes["XOR"],
                xk,
                opcodes["ADD"],
                add,
                opcodes["SUB"],
                sub,
                opcodes["ROL"],
                rol,
                opcodes["ROR"],
                ror,
                opcodes["MIX"],
                mix,
                opcodes["CMP"],
                v,
            ]
        )
        instructions.append({"index": i, "xor": xk, "add": add, "sub": sub, "rol": rol, "ror": ror, "mix": mix, "expected": v})
    program.extend([opcodes["HALT"], state & 0xFF, (state >> 8) & 0xFF, (state >> 16) & 0xFF, (state >> 24) & 0xFF])
    decoy_block = [rng.choice(list(opcodes.values())) if i % 2 == 0 else rng.randint(0, 255) for i in range(64)]
    program.extend(decoy_block)
    bytecode_key = rng.randint(1, 255)
    encoded = [b ^ ((bytecode_key + i * 13) & 0xFF) for i, b in enumerate(program)]
    recipe.encoding_chain = ["encoded randomized bytecode", "custom vm", "final state hash"]
    recipe.checker_type = "real-toy-vm"
    recipe.constants.update(
        {
            "opcodes": opcodes,
            "bytecode_key": bytecode_key,
            "encoded_bytecode": encoded,
            "bytecode_length": len(encoded),
            "instructions": instructions,
            "initial_state": initial_state,
            "final_state": state,
            "decoy_block_length": len(decoy_block),
        }
    )
    recipe.stages = instructions
    recipe.transformations = ["decode bytecode", "execute VM", "compare final state"]
    recipe.operations = names
    recipe.checker_logic = "A randomized VM executes encoded bytecode over the input and validates the final hash."


def _prep_superhard_symbolic_constraints(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    muls, adds, targets = _byte_mod_constraints(flag_bytes, rng)
    pairs = []
    triples = []
    for _ in range(max(12, len(flag_bytes))):
        i, j = rng.sample(range(len(flag_bytes)), 2)
        pairs.append({"i": i, "j": j, "sum": flag_bytes[i] + flag_bytes[j], "xor": flag_bytes[i] ^ flag_bytes[j]})
    for _ in range(max(8, len(flag_bytes) // 2)):
        i, j, k = rng.sample(range(len(flag_bytes)), 3)
        triples.append(
            {
                "i": i,
                "j": j,
                "k": k,
                "mod": 257,
                "value": (flag_bytes[i] * 3 + flag_bytes[j] * 5 + flag_bytes[k] * 7) % 257,
            }
        )
    recipe.encoding_chain = ["many modular constraints", "pair relationships", "triple relationships"]
    recipe.checker_type = "symbolic-constraint-system"
    recipe.constants.update({"modulus": 257, "muls": muls, "adds": adds, "targets": targets, "pairs": pairs, "triples": triples})
    recipe.transformations = ["unary modular equations", "pair sum/xor", "triple modular equations"]
    recipe.operations = ["constraint loops", "backtracking-friendly system"]
    recipe.checker_logic = "The binary validates a generated system of byte constraints."


def _prep_superhard_state_vm_combo(recipe: ChallengeRecipe, rng: Random, flag_bytes: list[int]) -> None:
    _prep_hard_encoded_table(recipe, rng, flag_bytes)
    encoded_table = dict(recipe.constants)
    start = rng.randint(0, 0xFFFFFFFF)
    states = []
    state = start
    multipliers = [rng.choice([33, 131, 257, 65537]) for _ in flag_bytes]
    offsets = [rng.randint(0, 0xFFFFFFFF) for _ in flag_bytes]
    for i, b in enumerate(flag_bytes):
        state = ((state ^ (b + i)) * multipliers[i] + offsets[i]) & 0xFFFFFFFF
        states.append(state)
    names = ["LOAD_INPUT", "XOR", "ADD", "ROL", "MIX", "CMP", "HALT", "JMP", "JNZ", "NOP"]
    opcodes = _opcode_map(rng, names)
    program: list[int] = []
    vm_instructions = []
    for i, b in enumerate(flag_bytes):
        xk = rng.randint(1, 255)
        add = rng.randint(0, 255)
        rot = rng.randint(1, 7)
        mix = rng.randint(1, 255)
        expected = (_rotl8(((b ^ xk) + add) & 0xFF, rot) ^ mix) & 0xFF
        program.extend([opcodes["LOAD_INPUT"], i, opcodes["XOR"], xk, opcodes["ADD"], add, opcodes["ROL"], rot, opcodes["MIX"], mix, opcodes["CMP"], expected])
        vm_instructions.append({"index": i, "xor": xk, "add": add, "rot": rot, "mix": mix, "expected": expected})
    program.append(opcodes["HALT"])
    program.extend([rng.randint(0, 255) for _ in range(48)])
    bytecode_key = rng.randint(1, 255)
    encoded_bytecode = [b ^ ((bytecode_key + i * 9) & 0xFF) for i, b in enumerate(program)]
    recipe.encoding_chain = ["state machine", "encoded table", "vm bytecode"]
    recipe.checker_type = "state-vm-combo"
    recipe.constants = {
        "flag_length": len(flag_bytes),
        "encoded_table": encoded_table,
        "start_state": start,
        "multipliers": multipliers,
        "offsets": offsets,
        "states": states,
        "opcodes": opcodes,
        "bytecode_key": bytecode_key,
        "encoded_bytecode": encoded_bytecode,
        "bytecode_length": len(encoded_bytecode),
        "vm_instructions": vm_instructions,
    }
    recipe.stages = vm_instructions
    recipe.transformations = ["encoded table inversion", "state trace", "VM bytecode"]
    recipe.operations = names + ["state hash", "table decode"]
    recipe.checker_logic = "The candidate must satisfy an encoded table, a state trace, and a VM pass."


def _split_bytes(values: list[int], rng: Random, min_chunks: int, max_chunks: int) -> list[list[int]]:
    if len(values) <= min_chunks:
        return [values]
    target = rng.randint(min_chunks, min(max_chunks, max(2, len(values) // 2)))
    cuts = sorted(rng.sample(range(1, len(values)), k=min(target - 1, len(values) - 1)))
    last = 0
    chunks = []
    for cut in cuts:
        chunks.append(values[last:cut])
        last = cut
    chunks.append(values[last:])
    return [chunk for chunk in chunks if chunk]


def _byte_mod_constraints(flag_bytes: list[int], rng: Random) -> tuple[list[int], list[int], list[int]]:
    muls = [rng.randint(1, 255) for _ in flag_bytes]
    adds = [rng.randint(0, 256) for _ in flag_bytes]
    targets = [((b * muls[i]) + adds[i]) % 257 for i, b in enumerate(flag_bytes)]
    return muls, adds, targets


def _rolling_hash(chunk: list[int], seed: int) -> int:
    h = seed & 0xFFFFFFFF
    for b in chunk:
        h = ((h ^ b) * 16777619 + 0x9E3779B9) & 0xFFFFFFFF
        h ^= h >> 13
    return h & 0xFFFFFFFF


def _custom_crc(chunk: list[int], seed: int) -> int:
    crc = seed ^ 0xA5A5A5A5
    for b in chunk:
        crc ^= b
        for _ in range(8):
            mask = -(crc & 1) & 0xEDB88320
            crc = ((crc >> 1) ^ mask) & 0xFFFFFFFF
    return crc ^ 0xFFFFFFFF


def _rotl8(value: int, amount: int) -> int:
    amount &= 7
    return ((value << amount) | (value >> (8 - amount))) & 0xFF


def _ror8(value: int, amount: int) -> int:
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xFF


def _opcode_map(rng: Random, names: list[str]) -> dict[str, int]:
    values = rng.sample(range(1, 245), len(names))
    return dict(zip(names, values))


def _matrix_rows(rows: list[list[int]], width: int = 16) -> str:
    rendered = []
    for row in rows:
        rendered.append("    {\n" + c_array(row, width=width) + "\n    }")
    return ",\n".join(rendered)


def _fake_string_block(recipe: ChallengeRecipe) -> str:
    values = recipe.fake_strings + recipe.fake_flags
    lines = ",\n".join(f"    {c_string(value)}" for value in values)
    return f"""static const char *rf_decoys[] = {{
{lines}
}};

static void rf_touch_decoys(void) {{
    volatile unsigned int total = 0;
    for (unsigned int i = 0; i < (unsigned int)(sizeof(rf_decoys) / sizeof(rf_decoys[0])); i++) {{
        total += (unsigned char)rf_decoys[i][0];
    }}
    if (total == 0xFFFFFFFFu) {{
        puts(rf_decoys[0]);
    }}
}}
"""


def _common_helpers() -> str:
    return """static unsigned int rf_rotl8(unsigned int value, unsigned int amount) {
    amount &= 7u;
    return ((value << amount) | (value >> (8u - amount))) & 0xFFu;
}

static unsigned int rf_ror8(unsigned int value, unsigned int amount) {
    amount &= 7u;
    return ((value >> amount) | (value << (8u - amount))) & 0xFFu;
}

static uint32_t rf_roll_hash(const unsigned char *data, size_t len, uint32_t seed) {
    uint32_t h = seed;
    for (size_t i = 0; i < len; i++) {
        h = ((h ^ data[i]) * 16777619u + 0x9E3779B9u) & 0xFFFFFFFFu;
        h ^= h >> 13u;
    }
    return h;
}

static uint32_t rf_custom_crc(const unsigned char *data, size_t len, uint32_t seed) {
    uint32_t crc = seed ^ 0xA5A5A5A5u;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (unsigned int bit = 0; bit < 8u; bit++) {
            uint32_t mask = (uint32_t)(-(int)(crc & 1u)) & 0xEDB88320u;
            crc = (crc >> 1u) ^ mask;
        }
    }
    return crc ^ 0xFFFFFFFFu;
}
"""


def _wrap_cli(recipe: ChallengeRecipe, checker: str) -> str:
    check = recipe.function_names["check"]
    return f"""/* Created by {CREATED_BY} */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *rf_banner = {c_string(BANNER)};

{_common_helpers()}
{_fake_string_block(recipe)}
{checker}

int main(int argc, char **argv) {{
    char input_buf[512] = {{0}};
    puts(rf_banner);
    if (argc > 1) {{
        snprintf(input_buf, sizeof(input_buf), "%s", argv[1]);
    }} else {{
        fputs("flag> ", stdout);
        if (fgets(input_buf, sizeof(input_buf), stdin) == NULL) {{
            puts({c_string(recipe.failure_message)});
            return 1;
        }}
        input_buf[strcspn(input_buf, "\\r\\n")] = '\\0';
    }}
    rf_touch_decoys();
    if ({check}(input_buf)) {{
        puts({c_string(recipe.success_message)});
        return 0;
    }}
    puts({c_string(recipe.failure_message)});
    return 1;
}}
"""


def _wrap_android(recipe: ChallengeRecipe, checker: str) -> str:
    check = recipe.function_names["check"]
    return f"""/* Created by {CREATED_BY} */
#include <jni.h>
#include <stdint.h>
#include <string.h>

static const char *rf_banner = {c_string(BANNER)};

static void puts(const char *unused) {{
    (void)unused;
}}

{_common_helpers()}
{_fake_string_block(recipe)}
{checker}

extern "C" JNIEXPORT jstring JNICALL
Java_com_revforge_challenge_MainActivity_banner(JNIEnv *env, jobject thiz) {{
    (void)thiz;
    return env->NewStringUTF(rf_banner);
}}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_revforge_challenge_MainActivity_checkFlag(JNIEnv *env, jobject thiz, jstring candidate) {{
    (void)thiz;
    const char *value = env->GetStringUTFChars(candidate, 0);
    int ok = {check}(value);
    env->ReleaseStringUTFChars(candidate, value);
    return ok ? JNI_TRUE : JNI_FALSE;
}}
"""


def _checker_code(recipe: ChallengeRecipe) -> str:
    renderers = {
        "baby_strings": _baby_strings,
        "baby_reverse": _baby_reverse,
        "baby_caesar": _baby_caesar,
        "easy_xor_chunks": _easy_xor_chunks,
        "easy_arithmetic_check": _easy_arithmetic_check,
        "easy_permutation": _easy_permutation,
        "medium_multi_stage": _medium_multi_stage,
        "medium_crc_gate": _medium_crc_gate,
        "medium_table_vm_lite": _medium_table_vm_lite,
        "hard_state_machine": _hard_state_machine,
        "hard_mixed_constraints": _hard_mixed_constraints,
        "hard_encoded_table": _hard_encoded_table,
        "superhard_toy_vm_real": _superhard_toy_vm_real,
        "superhard_symbolic_constraints": _superhard_symbolic_constraints,
        "superhard_state_vm_combo": _superhard_state_vm_combo,
    }
    try:
        return renderers[recipe.template_family](recipe)
    except KeyError as exc:
        raise ValueError(f"renderer is not implemented: {recipe.template_family}") from exc


def _baby_strings(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    return f"""static int {check}(const char *candidate) {{
    return strcmp(candidate, {c_string(recipe.constants["expected"])}) == 0;
}}
"""


def _baby_reverse(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    length = recipe.constants["flag_length"]
    reversed_flag = recipe.constants["reversed_flag"]
    return f"""static int {check}(const char *candidate) {{
    const char *expected_reversed = {c_string(reversed_flag)};
    size_t n = strlen(candidate);
    if (n != {length}u) return 0;
    for (size_t i = 0; i < n; i++) {{
        if ((unsigned char)candidate[i] != (unsigned char)expected_reversed[n - 1u - i]) return 0;
    }}
    return 1;
}}
"""


def _baby_caesar(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    c = recipe.constants
    return f"""static const unsigned int rf_encoded[] = {{
{c_array(c["encoded"])}
}};

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int v = ((unsigned char)candidate[i] + {c["shift"]}u) & 0xFFu;
        if (v != rf_encoded[i]) return 0;
    }}
    return 1;
}}
"""


def _easy_xor_chunks(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    c = recipe.constants
    arrays = []
    offset = 0
    calls = []
    for i, encoded in enumerate(c["encoded_chunks"]):
        arrays.append(f"""static const unsigned int rf_chunk_{i}[] = {{
{c_array(encoded)}
}};
""")
        calls.append(f"""    for (size_t j = 0; j < {len(encoded)}u; j++) {{
        if ((((unsigned char)candidate[{offset}u + j]) ^ {c["keys"][i]}u) != rf_chunk_{i}[j]) return 0;
    }}""")
        offset += len(encoded)
    return "\n".join(arrays) + f"""
static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
{chr(10).join(calls)}
    return 1;
}}
"""


def _easy_arithmetic_check(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    c = recipe.constants
    return f"""static const unsigned int rf_muls[] = {{
{c_array(c["muls"])}
}};
static const unsigned int rf_adds[] = {{
{c_array(c["adds"])}
}};
static const unsigned int rf_targets[] = {{
{c_array(c["targets"])}
}};

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int b = (unsigned char)candidate[i];
        if (((b * rf_muls[i]) + rf_adds[i]) % 257u != rf_targets[i]) return 0;
    }}
    return 1;
}}
"""


def _easy_permutation(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    c = recipe.constants
    return f"""static const unsigned int rf_perm[] = {{
{c_array(c["permutation"])}
}};
static const unsigned int rf_encoded[] = {{
{c_array(c["encoded"])}
}};

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int key = ({c["key"]}u + (unsigned int)i * 17u) & 0xFFu;
        unsigned int v = ((unsigned char)candidate[rf_perm[i]]) ^ key;
        if (v != rf_encoded[i]) return 0;
    }}
    return 1;
}}
"""


def _medium_multi_stage(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    f = recipe.function_names
    c = recipe.constants
    return f"""static const unsigned int rf_prefix[] = {{ {", ".join(str(v) for v in c["prefix_values"])} }};
static const unsigned int rf_suffix[] = {{ {", ".join(str(v) for v in c["suffix_values"])} }};
static const unsigned int rf_muls[] = {{
{c_array(c["muls"])}
}};
static const unsigned int rf_adds[] = {{
{c_array(c["adds"])}
}};
static const unsigned int rf_targets[] = {{
{c_array(c["targets"])}
}};
static const unsigned int rf_chunk_lengths[] = {{ {", ".join(str(v) for v in c["chunk_lengths"])} }};
static const uint32_t rf_chunk_seeds[] = {{ {", ".join(str(v) + "u" for v in c["chunk_seeds"])} }};
static const uint32_t rf_chunk_hashes[] = {{ {", ".join(str(v) + "u" for v in c["chunk_hashes"])} }};
static const unsigned int rf_perm[] = {{
{c_array(c["permutation"])}
}};
static const unsigned int rf_lookup[] = {{
{c_array(c["lookup"])}
}};

static int {f["stage"]}_0(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    for (size_t i = 0; i < sizeof(rf_prefix) / sizeof(rf_prefix[0]); i++) {{
        if ((unsigned char)candidate[i] != rf_prefix[i]) return 0;
    }}
    for (size_t i = 0; i < sizeof(rf_suffix) / sizeof(rf_suffix[0]); i++) {{
        if ((unsigned char)candidate[{c["flag_length"]}u - 1u - i] != rf_suffix[sizeof(rf_suffix) / sizeof(rf_suffix[0]) - 1u - i]) return 0;
    }}
    return 1;
}}

static int {f["stage"]}_1(const char *candidate) {{
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int b = (unsigned char)candidate[i];
        if (((b * rf_muls[i]) + rf_adds[i]) % 257u != rf_targets[i]) return 0;
    }}
    return 1;
}}

static int {f["stage"]}_2(const char *candidate) {{
    size_t offset = 0;
    for (size_t i = 0; i < sizeof(rf_chunk_lengths) / sizeof(rf_chunk_lengths[0]); i++) {{
        uint32_t h = rf_roll_hash((const unsigned char *)candidate + offset, rf_chunk_lengths[i], rf_chunk_seeds[i]);
        if (h != rf_chunk_hashes[i]) return 0;
        offset += rf_chunk_lengths[i];
    }}
    return 1;
}}

static int {f["stage"]}_3(const char *candidate) {{
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int v = (((unsigned char)candidate[rf_perm[i]]) ^ {c["lookup_key"]}u) + (unsigned int)i * 11u;
        if ((v & 0xFFu) != rf_lookup[i]) return 0;
    }}
    return 1;
}}

static int {check}(const char *candidate) {{
    return {f["stage"]}_0(candidate) && {f["stage"]}_1(candidate) && {f["stage"]}_2(candidate) && {f["stage"]}_3(candidate);
}}
"""


def _medium_crc_gate(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    f = recipe.function_names
    c = recipe.constants
    return f"""static const unsigned int rf_chunk_lengths[] = {{ {", ".join(str(v) for v in c["chunk_lengths"])} }};
static const uint32_t rf_crc_seeds[] = {{ {", ".join(str(v) + "u" for v in c["crc_seeds"])} }};
static const uint32_t rf_crc_targets[] = {{ {", ".join(str(v) + "u" for v in c["crc_targets"])} }};
static const uint32_t rf_decoy_targets[] = {{ {", ".join(str(v) + "u" for v in c["decoy_crc_targets"])} }};
static const unsigned int rf_xors[] = {{
{c_array(c["xors"])}
}};
static const unsigned int rf_adds[] = {{
{c_array(c["adds"])}
}};
static const unsigned int rf_targets[] = {{
{c_array(c["targets"])}
}};

static int {f["gate"]}_crc(const char *candidate) {{
    size_t offset = 0;
    uint32_t decoy = 0;
    for (size_t i = 0; i < sizeof(rf_chunk_lengths) / sizeof(rf_chunk_lengths[0]); i++) {{
        uint32_t got = rf_custom_crc((const unsigned char *)candidate + offset, rf_chunk_lengths[i], rf_crc_seeds[i]);
        decoy ^= got + rf_decoy_targets[i % (sizeof(rf_decoy_targets) / sizeof(rf_decoy_targets[0]))];
        if (got != rf_crc_targets[i]) return 0;
        offset += rf_chunk_lengths[i];
    }}
    if (decoy == 0xFFFFFFFFu) return 0;
    return 1;
}}

static int {f["gate"]}_bytes(const char *candidate) {{
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int v = ((((unsigned char)candidate[i]) ^ rf_xors[i]) + rf_adds[i] + (unsigned int)i) & 0xFFu;
        if (v != rf_targets[i]) return 0;
    }}
    return 1;
}}

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    return {f["gate"]}_crc(candidate) && {f["gate"]}_bytes(candidate);
}}
"""


def _medium_table_vm_lite(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    f = recipe.function_names
    c = recipe.constants
    op = c["opcodes"]
    return f"""static const unsigned int rf_program[] = {{
{c_array(c["program"])}
}};

static int {f["vm"]}_lite(const char *candidate) {{
    unsigned int acc = 0;
    size_t pc = 0;
    for (;;) {{
        unsigned int op = rf_program[pc++];
        if (op == {op["LOAD"]}u) acc = (unsigned char)candidate[rf_program[pc++]];
        else if (op == {op["XOR"]}u) acc = (acc ^ rf_program[pc++]) & 0xFFu;
        else if (op == {op["ADD"]}u) acc = (acc + rf_program[pc++]) & 0xFFu;
        else if (op == {op["ROL"]}u) acc = rf_rotl8(acc, rf_program[pc++]);
        else if (op == {op["MIX"]}u) acc = (acc ^ rf_program[pc++]) & 0xFFu;
        else if (op == {op["CMP"]}u) {{
            unsigned int expected = rf_program[pc++];
            if (((acc + (pc / 12u) - 1u) & 0xFFu) != expected) return 0;
        }}
        else if (op == {op["HALT"]}u) return 1;
        else return 0;
    }}
}}

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    return {f["vm"]}_lite(candidate);
}}
"""


def _hard_state_machine(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    f = recipe.function_names
    c = recipe.constants
    return f"""static const unsigned int rf_transitions[{c["state_count"]}][{c["alphabet_size"]}] = {{
{_matrix_rows(c["transition_table"])}
}};
static const unsigned int rf_keys[] = {{
{c_array(c["keys"])}
}};
static const unsigned int rf_pos_targets[] = {{
{c_array(c["pos_targets"])}
}};

static unsigned int {f["step"]}(unsigned int state, unsigned int byte) {{
    if (byte >= {c["alphabet_size"]}u || state >= {c["state_count"]}u) return {c["dead_state"]}u;
    return rf_transitions[state][byte];
}}

static int {f["guard"]}(const char *candidate, size_t index) {{
    unsigned int b = (unsigned char)candidate[index];
    return (((b ^ rf_keys[index]) + (unsigned int)index * 3u) & 0xFFu) == rf_pos_targets[index];
}}

static unsigned int {f["noise"]}(unsigned int state, unsigned int byte) {{
    return ((state << 5u) ^ (state >> 2u) ^ byte ^ 0xA7u) & 0xFFFFu;
}}

static int {f["accept"]}(unsigned int state) {{
    return state == {c["accept_state"]}u;
}}

static int {f["branch"]}(unsigned int value) {{
    return value != 0xDEADu;
}}

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    unsigned int state = {c["start_state"]}u;
    unsigned int noise = 0;
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int b = (unsigned char)candidate[i];
        if (!{f["guard"]}(candidate, i)) return 0;
        state = {f["step"]}(state, b);
        noise ^= {f["noise"]}(state, b);
        if (state == {c["dead_state"]}u) return 0;
    }}
    return {f["accept"]}(state) && {f["branch"]}(noise);
}}
"""


def _hard_mixed_constraints(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    f = recipe.function_names
    c = recipe.constants
    pairs = c["pairs"]
    return f"""static const unsigned int rf_muls[] = {{
{c_array(c["muls"])}
}};
static const unsigned int rf_adds[] = {{
{c_array(c["adds"])}
}};
static const unsigned int rf_targets[] = {{
{c_array(c["targets"])}
}};
static const unsigned int rf_pairs[][4] = {{
{_matrix_rows([[p["i"], p["j"], p["sum"], p["xor"]] for p in pairs], width=4)}
}};

static int {f["constraint"]}_unary(const char *candidate) {{
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int b = (unsigned char)candidate[i];
        if (((b * rf_muls[i]) + rf_adds[i]) % 257u != rf_targets[i]) return 0;
    }}
    return 1;
}}

static int {f["constraint"]}_sum(unsigned int a, unsigned int b, unsigned int expected) {{
    return a + b == expected;
}}

static int {f["constraint"]}_xor(unsigned int a, unsigned int b, unsigned int expected) {{
    return (a ^ b) == expected;
}}

static int {f["constraint"]}_pairs(const char *candidate) {{
    for (size_t p = 0; p < sizeof(rf_pairs) / sizeof(rf_pairs[0]); p++) {{
        unsigned int a = (unsigned char)candidate[rf_pairs[p][0]];
        unsigned int b = (unsigned char)candidate[rf_pairs[p][1]];
        if (!{f["constraint"]}_sum(a, b, rf_pairs[p][2])) return 0;
        if (!{f["constraint"]}_xor(a, b, rf_pairs[p][3])) return 0;
    }}
    return 1;
}}

static int {f["branch"]}(const char *candidate) {{
    return candidate[0] != '\\0';
}}

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    return {f["branch"]}(candidate) && {f["constraint"]}_unary(candidate) && {f["constraint"]}_pairs(candidate);
}}
"""


def _hard_encoded_table(recipe: ChallengeRecipe) -> str:
    return _hard_encoded_table_code(recipe, prefix="rf")


def _hard_encoded_table_code(recipe: ChallengeRecipe, prefix: str = "rf", constants: dict[str, Any] | None = None) -> str:
    check = recipe.function_names["check"] if prefix == "rf" else recipe.function_names["table"]
    f = recipe.function_names
    c = constants or recipe.constants
    return f"""static const unsigned int {prefix}_xors[] = {{
{c_array(c["xors"])}
}};
static const unsigned int {prefix}_adds[] = {{
{c_array(c["adds"])}
}};
static const unsigned int {prefix}_rots[] = {{
{c_array(c["rots"])}
}};
static const unsigned int {prefix}_masks[] = {{
{c_array(c["masks"])}
}};
static const unsigned int {prefix}_encoded[] = {{
{c_array(c["encoded"])}
}};

static unsigned int {f["decode"]}_a(size_t i, unsigned int b) {{
    return (b ^ {prefix}_xors[i]) & 0xFFu;
}}

static unsigned int {f["decode"]}_b(size_t i, unsigned int b) {{
    return (b + {prefix}_adds[i] + (unsigned int)i) & 0xFFu;
}}

static unsigned int {f["decode"]}_c(size_t i, unsigned int b) {{
    return rf_rotl8(b, {prefix}_rots[i]) ^ {prefix}_masks[i];
}}

static int {f["decode"]}_d(size_t i, unsigned int b) {{
    unsigned int v = {f["decode"]}_a(i, b);
    v = {f["decode"]}_b(i, v);
    v = {f["decode"]}_c(i, v);
    return v == {prefix}_encoded[i];
}}

static int {f["guard"]}_table(const char *candidate) {{
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        if (!{f["decode"]}_d(i, (unsigned char)candidate[i])) return 0;
    }}
    return 1;
}}

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    return {f["guard"]}_table(candidate);
}}
"""


def _superhard_toy_vm_real(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    f = recipe.function_names
    c = recipe.constants
    op = c["opcodes"]
    return f"""static const unsigned int rf_encoded_bytecode[] = {{
{c_array(c["encoded_bytecode"])}
}};

static unsigned int {f["decode"]}_byte(size_t pc) {{
    return (rf_encoded_bytecode[pc] ^ (({c["bytecode_key"]}u + (unsigned int)pc * 13u) & 0xFFu)) & 0xFFu;
}}

static unsigned int {f["vm"]}_fetch(size_t *pc) {{
    unsigned int value = {f["decode"]}_byte(*pc);
    *pc += 1u;
    return value;
}}

static unsigned int {f["mix"]}_xor(unsigned int acc, unsigned int value) {{ return (acc ^ value) & 0xFFu; }}
static unsigned int {f["mix"]}_add(unsigned int acc, unsigned int value) {{ return (acc + value) & 0xFFu; }}
static unsigned int {f["mix"]}_sub(unsigned int acc, unsigned int value) {{ return (acc - value) & 0xFFu; }}
static unsigned int {f["mix"]}_rol(unsigned int acc, unsigned int value) {{ return rf_rotl8(acc, value); }}
static unsigned int {f["mix"]}_ror(unsigned int acc, unsigned int value) {{ return rf_ror8(acc, value); }}
static unsigned int {f["mix"]}_mix(unsigned int acc, unsigned int value) {{ return (acc ^ value) & 0xFFu; }}
static uint32_t {f["hash"]}_update(uint32_t state, unsigned int acc, unsigned int mix, unsigned int index) {{
    return ((state ^ acc) * 16777619u + index + mix) & 0xFFFFFFFFu;
}}

static int {f["dispatch"]}(const char *candidate, uint32_t *state_out) {{
    size_t pc = 0;
    unsigned int acc = 0;
    unsigned int last_mix = 0;
    unsigned int cmp_index = 0;
    uint32_t state = {c["initial_state"]}u;
    for (;;) {{
        unsigned int op = {f["vm"]}_fetch(&pc);
        if (op == {op["LOAD_INPUT"]}u) {{
            unsigned int index = {f["vm"]}_fetch(&pc);
            if (index >= {c["flag_length"]}u) return 0;
            acc = (unsigned char)candidate[index];
            cmp_index = index;
        }} else if (op == {op["XOR"]}u) acc = {f["mix"]}_xor(acc, {f["vm"]}_fetch(&pc));
        else if (op == {op["ADD"]}u) acc = {f["mix"]}_add(acc, {f["vm"]}_fetch(&pc));
        else if (op == {op["SUB"]}u) acc = {f["mix"]}_sub(acc, {f["vm"]}_fetch(&pc));
        else if (op == {op["ROL"]}u) acc = {f["mix"]}_rol(acc, {f["vm"]}_fetch(&pc));
        else if (op == {op["ROR"]}u) acc = {f["mix"]}_ror(acc, {f["vm"]}_fetch(&pc));
        else if (op == {op["MIX"]}u) {{
            last_mix = {f["vm"]}_fetch(&pc);
            acc = {f["mix"]}_mix(acc, last_mix);
        }} else if (op == {op["CMP"]}u) {{
            unsigned int expected = {f["vm"]}_fetch(&pc);
            if (acc != expected) return 0;
            state = {f["hash"]}_update(state, acc, last_mix, cmp_index);
        }} else if (op == {op["JMP"]}u) {{
            pc = {f["vm"]}_fetch(&pc);
        }} else if (op == {op["JNZ"]}u) {{
            unsigned int target = {f["vm"]}_fetch(&pc);
            if (acc != 0) pc = target;
        }} else if (op == {op["NOP"]}u) {{
            acc ^= 0u;
        }} else if (op == {op["HALT"]}u) {{
            uint32_t expected = {f["vm"]}_fetch(&pc);
            expected |= {f["vm"]}_fetch(&pc) << 8u;
            expected |= {f["vm"]}_fetch(&pc) << 16u;
            expected |= {f["vm"]}_fetch(&pc) << 24u;
            *state_out = state;
            return state == expected;
        }} else return 0;
        if (pc >= {c["bytecode_length"]}u) return 0;
    }}
}}

static int {check}(const char *candidate) {{
    uint32_t state = 0;
    if (strlen(candidate) != {c["flag_length"]}u) return 0;
    return {f["dispatch"]}(candidate, &state);
}}
"""


def _superhard_symbolic_constraints(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    f = recipe.function_names
    c = recipe.constants
    pairs = [[p["i"], p["j"], p["sum"], p["xor"]] for p in c["pairs"]]
    triples = [[t["i"], t["j"], t["k"], t["value"]] for t in c["triples"]]
    return f"""static const unsigned int rf_muls[] = {{
{c_array(c["muls"])}
}};
static const unsigned int rf_adds[] = {{
{c_array(c["adds"])}
}};
static const unsigned int rf_targets[] = {{
{c_array(c["targets"])}
}};
static const unsigned int rf_pairs[][4] = {{
{_matrix_rows(pairs, width=4)}
}};
static const unsigned int rf_triples[][4] = {{
{_matrix_rows(triples, width=4)}
}};

static int {f["constraint"]}_u0(unsigned int b, size_t i) {{ return ((b * rf_muls[i]) + rf_adds[i]) % 257u == rf_targets[i]; }}
static int {f["constraint"]}_u1(const char *candidate) {{
    for (size_t i = 0; i < {c["flag_length"]}u; i++) if (!{f["constraint"]}_u0((unsigned char)candidate[i], i)) return 0;
    return 1;
}}
static int {f["constraint"]}_p0(unsigned int a, unsigned int b, unsigned int s) {{ return a + b == s; }}
static int {f["constraint"]}_p1(unsigned int a, unsigned int b, unsigned int x) {{ return (a ^ b) == x; }}
static int {f["constraint"]}_p2(const char *candidate) {{
    for (size_t i = 0; i < sizeof(rf_pairs) / sizeof(rf_pairs[0]); i++) {{
        unsigned int a = (unsigned char)candidate[rf_pairs[i][0]];
        unsigned int b = (unsigned char)candidate[rf_pairs[i][1]];
        if (!{f["constraint"]}_p0(a, b, rf_pairs[i][2])) return 0;
        if (!{f["constraint"]}_p1(a, b, rf_pairs[i][3])) return 0;
    }}
    return 1;
}}
static int {f["constraint"]}_t0(unsigned int a, unsigned int b, unsigned int c, unsigned int value) {{
    return (a * 3u + b * 5u + c * 7u) % 257u == value;
}}
static int {f["constraint"]}_t1(const char *candidate) {{
    for (size_t i = 0; i < sizeof(rf_triples) / sizeof(rf_triples[0]); i++) {{
        unsigned int a = (unsigned char)candidate[rf_triples[i][0]];
        unsigned int b = (unsigned char)candidate[rf_triples[i][1]];
        unsigned int c = (unsigned char)candidate[rf_triples[i][2]];
        if (!{f["constraint"]}_t0(a, b, c, rf_triples[i][3])) return 0;
    }}
    return 1;
}}
static int {f["branch"]}_s0(const char *candidate) {{ return candidate[0] != '\\0'; }}
static int {f["branch"]}_s1(const char *candidate) {{ return strlen(candidate) == {c["flag_length"]}u; }}

static int {check}(const char *candidate) {{
    return {f["branch"]}_s1(candidate) && {f["branch"]}_s0(candidate) && {f["constraint"]}_u1(candidate) && {f["constraint"]}_p2(candidate) && {f["constraint"]}_t1(candidate);
}}
"""


def _superhard_state_vm_combo(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    f = recipe.function_names
    c = recipe.constants
    table = c["encoded_table"]
    op = c["opcodes"]
    return f"""static const unsigned int rf_combo_xors[] = {{
{c_array(table["xors"])}
}};
static const unsigned int rf_combo_adds[] = {{
{c_array(table["adds"])}
}};
static const unsigned int rf_combo_rots[] = {{
{c_array(table["rots"])}
}};
static const unsigned int rf_combo_masks[] = {{
{c_array(table["masks"])}
}};
static const unsigned int rf_combo_encoded[] = {{
{c_array(table["encoded"])}
}};
static const unsigned int rf_mults[] = {{
{c_array(c["multipliers"])}
}};
static const uint32_t rf_offsets[] = {{ {", ".join(str(v) + "u" for v in c["offsets"])} }};
static const uint32_t rf_states[] = {{ {", ".join(str(v) + "u" for v in c["states"])} }};
static const unsigned int rf_encoded_bytecode[] = {{
{c_array(c["encoded_bytecode"])}
}};

static unsigned int {f["decode"]}_combo_a(size_t i, unsigned int b) {{ return (b ^ rf_combo_xors[i]) & 0xFFu; }}
static unsigned int {f["decode"]}_combo_b(size_t i, unsigned int b) {{ return (b + rf_combo_adds[i] + (unsigned int)i) & 0xFFu; }}
static unsigned int {f["decode"]}_combo_c(size_t i, unsigned int b) {{ return rf_rotl8(b, rf_combo_rots[i]) ^ rf_combo_masks[i]; }}
static int {f["table"]}_combo(const char *candidate) {{
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        unsigned int v = {f["decode"]}_combo_a(i, (unsigned char)candidate[i]);
        v = {f["decode"]}_combo_b(i, v);
        v = {f["decode"]}_combo_c(i, v);
        if (v != rf_combo_encoded[i]) return 0;
    }}
    return 1;
}}
static int {f["step"]}_combo(const char *candidate) {{
    uint32_t state = {c["start_state"]}u;
    for (size_t i = 0; i < {c["flag_length"]}u; i++) {{
        state = ((state ^ ((unsigned char)candidate[i] + (uint32_t)i)) * rf_mults[i] + rf_offsets[i]) & 0xFFFFFFFFu;
        if (state != rf_states[i]) return 0;
    }}
    return 1;
}}
static unsigned int {f["vm"]}_combo_byte(size_t pc) {{ return (rf_encoded_bytecode[pc] ^ (({c["bytecode_key"]}u + (unsigned int)pc * 9u) & 0xFFu)) & 0xFFu; }}
static unsigned int {f["vm"]}_combo_fetch(size_t *pc) {{ unsigned int v = {f["vm"]}_combo_byte(*pc); *pc += 1u; return v; }}
static int {f["dispatch"]}_combo(const char *candidate) {{
    size_t pc = 0;
    unsigned int acc = 0;
    for (;;) {{
        unsigned int code = {f["vm"]}_combo_fetch(&pc);
        if (code == {op["LOAD_INPUT"]}u) acc = (unsigned char)candidate[{f["vm"]}_combo_fetch(&pc)];
        else if (code == {op["XOR"]}u) acc = (acc ^ {f["vm"]}_combo_fetch(&pc)) & 0xFFu;
        else if (code == {op["ADD"]}u) acc = (acc + {f["vm"]}_combo_fetch(&pc)) & 0xFFu;
        else if (code == {op["ROL"]}u) acc = rf_rotl8(acc, {f["vm"]}_combo_fetch(&pc));
        else if (code == {op["MIX"]}u) acc = (acc ^ {f["vm"]}_combo_fetch(&pc)) & 0xFFu;
        else if (code == {op["CMP"]}u) {{ if (acc != {f["vm"]}_combo_fetch(&pc)) return 0; }}
        else if (code == {op["HALT"]}u) return 1;
        else if (code == {op["JMP"]}u) pc = {f["vm"]}_combo_fetch(&pc);
        else if (code == {op["JNZ"]}u) {{ unsigned int target = {f["vm"]}_combo_fetch(&pc); if (acc != 0) pc = target; }}
        else if (code == {op["NOP"]}u) acc ^= 0u;
        else return 0;
        if (pc >= {c["bytecode_length"]}u) return 0;
    }}
}}
static int {f["guard"]}_combo(const char *candidate) {{ return strlen(candidate) == {c["flag_length"]}u; }}
static int {f["branch"]}_combo(const char *candidate) {{ return candidate[0] != '\\0'; }}

static int {check}(const char *candidate) {{
    return {f["guard"]}_combo(candidate) && {f["branch"]}_combo(candidate) && {f["table"]}_combo(candidate) && {f["step"]}_combo(candidate) && {f["dispatch"]}_combo(candidate);
}}
"""


def _solution_script(recipe: ChallengeRecipe) -> str:
    template = recipe.template_family
    c = recipe.constants
    if template == "baby_strings":
        body = f"expected = {recipe.flag!r}\nprint(expected)\n"
    elif template == "baby_reverse":
        body = f"reversed_value = {c['reversed_flag']!r}\nprint(reversed_value[::-1])\n"
    elif template == "baby_caesar":
        body = f"encoded = {c['encoded']!r}\nshift = {c['shift']!r}\nprint(''.join(chr((b - shift) & 0xff) for b in encoded))\n"
    elif template == "easy_xor_chunks":
        body = f"""encoded_chunks = {c['encoded_chunks']!r}
keys = {c['keys']!r}
out = []
for chunk, key in zip(encoded_chunks, keys):
    out.extend(chr(b ^ key) for b in chunk)
print(''.join(out))
"""
    elif template in {"easy_arithmetic_check", "hard_mixed_constraints", "superhard_symbolic_constraints"}:
        extra = ""
        if template in {"hard_mixed_constraints", "superhard_symbolic_constraints"}:
            extra = f"""
pairs = {c.get('pairs', [])!r}
triples = {c.get('triples', [])!r}
def ok_extra(chars):
    values = [ord(ch) for ch in chars]
    for item in pairs:
        if values[item['i']] + values[item['j']] != item['sum']:
            return False
        if (values[item['i']] ^ values[item['j']]) != item['xor']:
            return False
    for item in triples:
        if (values[item['i']] * 3 + values[item['j']] * 5 + values[item['k']] * 7) % item['mod'] != item['value']:
            return False
    return True
"""
        body = f"""muls = {c['muls']!r}
adds = {c['adds']!r}
targets = {c['targets']!r}
out = []
for i, target in enumerate(targets):
    found = None
    for candidate in range(256):
        if ((candidate * muls[i]) + adds[i]) % 257 == target:
            found = candidate
            break
    if found is None:
        raise SystemExit(f'no byte for index {{i}}')
    out.append(chr(found))
{extra}
candidate = ''.join(out)
if 'ok_extra' in globals() and not ok_extra(candidate):
    raise SystemExit('constraint reconstruction failed')
print(candidate)
"""
    elif template == "easy_permutation":
        body = f"""permutation = {c['permutation']!r}
encoded = {c['encoded']!r}
key = {c['key']!r}
out = ['?'] * len(permutation)
for i, pos in enumerate(permutation):
    out[pos] = chr(encoded[i] ^ ((key + i * 17) & 0xff))
print(''.join(out))
"""
    elif template == "medium_multi_stage":
        body = f"""muls = {c['muls']!r}
adds = {c['adds']!r}
targets = {c['targets']!r}
out = []
for i, target in enumerate(targets):
    for candidate in range(256):
        if ((candidate * muls[i]) + adds[i]) % 257 == target:
            out.append(chr(candidate))
            break
    else:
        raise SystemExit(f'no byte for index {{i}}')
print(''.join(out))
"""
    elif template == "medium_crc_gate":
        body = f"""xors = {c['xors']!r}
adds = {c['adds']!r}
targets = {c['targets']!r}
out = []
for i, target in enumerate(targets):
    v = (target - adds[i] - i) & 0xff
    out.append(chr(v ^ xors[i]))
print(''.join(out))
"""
    elif template == "medium_table_vm_lite":
        body = _solve_vm_lite(c)
    elif template == "hard_state_machine":
        body = f"""keys = {c['keys']!r}
targets = {c['pos_targets']!r}
out = []
for i, target in enumerate(targets):
    for candidate in range(128):
        if (((candidate ^ keys[i]) + i * 3) & 0xff) == target:
            out.append(chr(candidate))
            break
    else:
        raise SystemExit(f'no byte for index {{i}}')
print(''.join(out))
"""
    elif template == "hard_encoded_table":
        body = _solve_encoded_table(c)
    elif template == "superhard_toy_vm_real":
        body = _solve_super_vm(c)
    elif template == "superhard_state_vm_combo":
        body = _solve_encoded_table(c["encoded_table"])
    else:
        body = "raise SystemExit('unsupported generated solver')\n"
    return f"""#!/usr/bin/env python3
# Created by {CREATED_BY}
\"\"\"Solver for this generated RevForge challenge.\"\"\"

{body}"""


def _solve_vm_lite(c: dict[str, Any]) -> str:
    return f"""def ror8(value, amount):
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xff

instructions = {c['instructions']!r}
out = ['?'] * len(instructions)
for item in instructions:
    v = (item['expected'] - item['index']) & 0xff
    v ^= item['mix']
    v = ror8(v, item['rot'])
    v = (v - item['add']) & 0xff
    v ^= item['xor']
    out[item['index']] = chr(v)
print(''.join(out))
"""


def _solve_encoded_table(c: dict[str, Any]) -> str:
    return f"""def ror8(value, amount):
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xff

xors = {c['xors']!r}
adds = {c['adds']!r}
rots = {c['rots']!r}
masks = {c['masks']!r}
encoded = {c['encoded']!r}
out = []
for i, value in enumerate(encoded):
    v = value ^ masks[i]
    v = ror8(v, rots[i])
    v = (v - adds[i] - i) & 0xff
    v ^= xors[i]
    out.append(chr(v))
print(''.join(out))
"""


def _solve_super_vm(c: dict[str, Any]) -> str:
    return f"""def rol8(value, amount):
    amount &= 7
    return ((value << amount) | (value >> (8 - amount))) & 0xff

def ror8(value, amount):
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xff

instructions = {c['instructions']!r}
out = ['?'] * len(instructions)
for item in instructions:
    v = item['expected'] ^ item['mix']
    v = rol8(v, item['ror'])
    v = ror8(v, item['rol'])
    v = (v + item['sub']) & 0xff
    v = (v - item['add']) & 0xff
    v ^= item['xor']
    out[item['index']] = chr(v)
print(''.join(out))
"""


def _writeup(recipe: ChallengeRecipe) -> str:
    return f"""# Writeup

Created by {CREATED_BY}

This generated challenge uses `{recipe.template_family}` at `{recipe.difficulty}` difficulty.

Intended reversing path:

1. Identify the generated checker functions from `main`.
2. Recover the encoded constants and control flow.
3. Recreate the validation algorithm in a small script.
4. Verify the reconstructed input against the binary.

The included `solution/solve.py` derives the answer from the generated recipe constants and validation logic.
"""
