"""Template preparation and source rendering."""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from ..flags import render_flag
from ..recipes import ChallengeRecipe, TEMPLATES_BY_DIFFICULTY
from ..utils import BANNER, CREATED_BY, c_array, c_string


@dataclass(frozen=True)
class TemplateRender:
    cli_source: str
    android_source: str
    solution: str
    writeup: str


SUCCESS_MESSAGES = [
    "Access granted. Training objective complete.",
    "Correct flag. Reverse engineering path verified.",
    "Nice work. The checker accepted the input.",
    "Signal matched. Challenge solved.",
]

FAILURE_MESSAGES = [
    "Access denied. Keep reversing.",
    "No match. Try another path.",
    "Rejected. The checker disagrees.",
    "Incorrect input.",
]

STORIES = [
    "A local validation routine guards a training console.",
    "The binary checks one candidate string and exits.",
    "A small crackme routine hides the expected input in generated logic.",
    "The challenge simulates a CTF key check without network or persistence.",
]

FAKE_STRINGS = [
    "debug_mode_enabled=false",
    "license_server=offline",
    "training_build_only",
    "do_not_submit_this_decoy",
    "analysis_note: local input only",
    "wrong branch reached",
]


def implemented_templates() -> dict[str, tuple[str, ...]]:
    return TEMPLATES_BY_DIFFICULTY


def prepare_recipe(recipe: ChallengeRecipe, rng: Random) -> ChallengeRecipe:
    recipe.success_message = rng.choice(SUCCESS_MESSAGES)
    recipe.failure_message = rng.choice(FAILURE_MESSAGES)
    recipe.story = rng.choice(STORIES)
    recipe.fake_strings = rng.sample(FAKE_STRINGS, k=rng.randint(2, 4))
    recipe.fake_flags = [
        render_flag(recipe.flag_format, f"decoy_{rng.getrandbits(16):04x}"),
        render_flag(recipe.flag_format, f"wrong_{rng.getrandbits(16):04x}"),
    ]
    recipe.compiler_flags = ["-std=c11", "-O2", "-Wall", "-Wextra"]

    flag_bytes = list(recipe.flag.encode("utf-8"))
    recipe.constants["flag_length"] = len(flag_bytes)

    template = recipe.template_family
    if template == "baby_plain":
        recipe.encoding_chain = ["plain-string-compare"]
        recipe.checker_type = "strcmp"
        recipe.constants["expected"] = recipe.flag
        recipe.transformations = ["none"]
        recipe.operations = ["strlen", "strcmp"]
        recipe.checker_logic = "Compare user input directly with the expected flag."
    elif template == "baby_reverse":
        recipe.encoding_chain = ["reverse"]
        recipe.checker_type = "reverse-index-compare"
        recipe.constants["reversed_flag"] = recipe.flag[::-1]
        recipe.transformations = ["reverse"]
        recipe.operations = ["strlen", "indexed compare"]
        recipe.checker_logic = "Compare each input character against a reversed constant."
    elif template == "baby_caesar":
        shift = rng.randint(1, 25)
        recipe.encoding_chain = ["caesar"]
        recipe.checker_type = "caesar-byte-compare"
        recipe.constants["shift"] = shift
        recipe.constants["encoded"] = [((b + shift) & 0xFF) for b in flag_bytes]
        recipe.transformations = [f"byte + {shift}"]
        recipe.operations = ["strlen", "byte addition"]
        recipe.checker_logic = "Shift each candidate byte and compare with encoded bytes."
    elif template == "easy_xor":
        key = rng.randint(1, 255)
        recipe.encoding_chain = ["xor"]
        recipe.checker_type = "xor-array"
        recipe.constants["xor_key"] = key
        recipe.constants["encoded"] = [b ^ key for b in flag_bytes]
        recipe.transformations = [f"xor {key}"]
        recipe.operations = ["strlen", "xor"]
        recipe.checker_logic = "XOR each byte with a randomized key and compare with an array."
    elif template == "easy_split":
        chunks = _split_chunks(recipe.flag, rng, 3, 6)
        order = list(range(len(chunks)))
        rng.shuffle(order)
        scrambled = [chunks[i] for i in order]
        restore = [order.index(i) for i in range(len(chunks))]
        recipe.encoding_chain = ["split", "scrambled-order"]
        recipe.checker_type = "chunk-reassembly"
        recipe.constants.update({"chunks": chunks, "scrambled_chunks": scrambled, "restore_order": restore})
        recipe.transformations = ["split chunks", "scramble chunk table"]
        recipe.operations = ["memcpy", "strcmp"]
        recipe.checker_logic = "Rebuild the expected flag from scrambled string fragments."
    elif template == "easy_math":
        adds = [rng.randint(1, 31) for _ in flag_bytes]
        targets = [b + adds[i] + (i % 7) for i, b in enumerate(flag_bytes)]
        checksum = sum((i + 3) * b for i, b in enumerate(flag_bytes)) & 0xFFFF
        recipe.encoding_chain = ["byte-add", "weighted-checksum"]
        recipe.checker_type = "math-constraints"
        recipe.constants.update({"adds": adds, "targets": targets, "checksum": checksum})
        recipe.transformations = ["per-byte addition", "weighted checksum"]
        recipe.operations = ["integer compare", "checksum"]
        recipe.checker_logic = "Validate byte arithmetic and a small checksum."
    elif template == "medium_xor_chain":
        keys = [rng.randint(1, 255) for _ in range(3)]
        encoded = []
        for i, b in enumerate(flag_bytes):
            v = b ^ keys[0]
            v = (v + keys[1] + i) & 0xFF
            v ^= keys[2]
            encoded.append(v)
        recipe.encoding_chain = ["xor", "index-add", "xor"]
        recipe.checker_type = "xor-chain"
        recipe.constants.update({"keys": keys, "encoded": encoded})
        recipe.transformations = [f"xor {keys[0]}", f"add {keys[1]} + index", f"xor {keys[2]}"]
        recipe.operations = ["xor", "addition", "array compare"]
        recipe.checker_logic = "Apply a chained reversible transform to every byte."
    elif template == "medium_chunked_flag":
        chunks = _split_chunks(recipe.flag, rng, 4, 7)
        keys = [rng.randint(1, 255) for _ in chunks]
        encoded_chunks = [[c.encode("utf-8")[i] ^ keys[index] for i in range(len(c.encode("utf-8")))] for index, c in enumerate(chunks)]
        order = list(range(len(chunks)))
        rng.shuffle(order)
        recipe.encoding_chain = ["chunk", "xor-per-chunk", "out-of-order-functions"]
        recipe.checker_type = "multi-function-chunks"
        recipe.constants.update({"chunks": chunks, "keys": keys, "encoded_chunks": encoded_chunks, "check_order": order})
        recipe.stages = [{"chunk": i, "key": keys[i], "length": len(chunks[i])} for i in range(len(chunks))]
        recipe.transformations = ["split chunks", "xor each chunk with different key"]
        recipe.operations = ["function calls", "xor", "offset compare"]
        recipe.checker_logic = "Validate flag chunks with separate randomized stage functions."
    elif template == "medium_arithmetic_validator":
        muls = [rng.randint(1, 255) for _ in flag_bytes]
        adds = [rng.randint(0, 255) for _ in flag_bytes]
        targets = [((b * muls[i]) + adds[i] + i) % 257 for i, b in enumerate(flag_bytes)]
        score = 0x811C9DC5
        for i, b in enumerate(flag_bytes):
            score = ((score * 33) ^ (b + targets[i] + i)) & 0xFFFFFFFF
        recipe.encoding_chain = ["mod-prime-arithmetic", "rolling-score"]
        recipe.checker_type = "arithmetic-validator"
        recipe.constants.update({"muls": muls, "adds": adds, "targets": targets, "score": score})
        recipe.transformations = ["per-byte modular arithmetic", "rolling score"]
        recipe.operations = ["mod 257", "uint32 rolling score"]
        recipe.checker_logic = "Check modular byte constraints and a rolling validation score."
    elif template == "hard_state_machine":
        start = rng.randint(0x1000, 0xFFFF)
        mults = [rng.choice([3, 5, 7, 11, 13, 17, 19]) for _ in flag_bytes]
        adds = [rng.randint(0, 0xFFFF) for _ in flag_bytes]
        states = []
        state = start
        for i, b in enumerate(flag_bytes):
            state = (((state ^ b) * mults[i]) + adds[i]) & 0xFFFF
            states.append(state)
        recipe.encoding_chain = ["state-machine"]
        recipe.checker_type = "state-machine"
        recipe.constants.update({"start": start, "mults": mults, "adds": adds, "states": states})
        recipe.transformations = ["xor input into state", "multiply", "add", "compare state trace"]
        recipe.operations = ["state transition", "decoy arithmetic"]
        recipe.checker_logic = "Walk a generated state machine and compare each intermediate state."
    elif template == "hard_multistage":
        xors = [rng.randint(1, 255) for _ in flag_bytes]
        adds = [rng.randint(0, 255) for _ in flag_bytes]
        rots = [rng.randint(1, 7) for _ in flag_bytes]
        posts = [rng.randint(1, 255) for _ in flag_bytes]
        encoded = []
        for i, b in enumerate(flag_bytes):
            v = (b ^ xors[i])
            v = (v + adds[i]) & 0xFF
            v = _rotl8(v, rots[i])
            v ^= posts[i]
            encoded.append(v)
        recipe.encoding_chain = ["xor", "add", "rotl", "xor"]
        recipe.checker_type = "multi-stage-encoded-table"
        recipe.constants.update({"xors": xors, "adds": adds, "rots": rots, "posts": posts, "encoded": encoded})
        recipe.transformations = ["xor", "add", "rotate left", "post xor"]
        recipe.operations = ["byte table", "rotl", "control-flow noise"]
        recipe.checker_logic = "Run every byte through a randomized multi-stage transform."
    elif template == "superhard_toy_vm":
        program: list[int] = []
        instructions: list[dict[str, int]] = []
        for i, b in enumerate(flag_bytes):
            xk = rng.randint(1, 255)
            add = rng.randint(0, 255)
            rot = rng.randint(1, 7)
            expected = _rotl8(((b ^ xk) + add) & 0xFF, rot)
            program.extend([1, i, 2, xk, 3, add, 4, rot, 5, expected])
            instructions.append({"index": i, "xor": xk, "add": add, "rot": rot, "expected": expected})
        program.append(255)
        recipe.encoding_chain = ["toy-vm-bytecode"]
        recipe.checker_type = "toy-vm"
        recipe.constants.update({"program": program, "instructions": instructions})
        recipe.stages = instructions
        recipe.transformations = ["LOAD_INPUT", "XOR", "ADD", "ROL", "CMP"]
        recipe.operations = ["bytecode interpreter", "switch dispatch", "decoy paths"]
        recipe.checker_logic = "Interpret generated bytecode that validates each byte of the flag."
    else:
        raise ValueError(f"template is not implemented: {template}")
    return recipe


def render(recipe: ChallengeRecipe) -> TemplateRender:
    checker = _checker_code(recipe)
    cli_source = _wrap_cli(recipe, checker)
    android_source = _wrap_android(recipe, checker)
    return TemplateRender(
        cli_source=cli_source,
        android_source=android_source,
        solution=_solution_script(recipe),
        writeup=_writeup(recipe),
    )


def _split_chunks(value: str, rng: Random, min_chunks: int, max_chunks: int) -> list[str]:
    if len(value) <= min_chunks:
        return [value]
    target = rng.randint(min_chunks, min(max_chunks, max(2, len(value) // 2)))
    cut_points = sorted(rng.sample(range(1, len(value)), k=min(target - 1, len(value) - 1)))
    last = 0
    chunks = []
    for cut in cut_points:
        chunks.append(value[last:cut])
        last = cut
    chunks.append(value[last:])
    return [chunk for chunk in chunks if chunk]


def _rotl8(value: int, amount: int) -> int:
    amount &= 7
    return ((value << amount) | (value >> (8 - amount))) & 0xFF


def _ror8(value: int, amount: int) -> int:
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xFF


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


def _wrap_cli(recipe: ChallengeRecipe, checker: str) -> str:
    check = recipe.function_names["check"]
    return f"""/* Created by {CREATED_BY} */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static const char *rf_banner = {c_string(BANNER)};

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
    template = recipe.template_family
    if template == "baby_plain":
        return _baby_plain(recipe)
    if template == "baby_reverse":
        return _baby_reverse(recipe)
    if template == "baby_caesar":
        return _baby_caesar(recipe)
    if template == "easy_xor":
        return _easy_xor(recipe)
    if template == "easy_split":
        return _easy_split(recipe)
    if template == "easy_math":
        return _easy_math(recipe)
    if template == "medium_xor_chain":
        return _medium_xor_chain(recipe)
    if template == "medium_chunked_flag":
        return _medium_chunked_flag(recipe)
    if template == "medium_arithmetic_validator":
        return _medium_arithmetic_validator(recipe)
    if template == "hard_state_machine":
        return _hard_state_machine(recipe)
    if template == "hard_multistage":
        return _hard_multistage(recipe)
    if template == "superhard_toy_vm":
        return _superhard_toy_vm(recipe)
    raise ValueError(f"renderer is not implemented: {template}")


def _baby_plain(recipe: ChallengeRecipe) -> str:
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
    if (n != {length}u) {{
        return 0;
    }}
    for (size_t i = 0; i < n; i++) {{
        if ((unsigned char)candidate[i] != (unsigned char)expected_reversed[n - 1u - i]) {{
            return 0;
        }}
    }}
    return 1;
}}
"""


def _baby_caesar(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    encoded = recipe.constants["encoded"]
    shift = recipe.constants["shift"]
    length = recipe.constants["flag_length"]
    return f"""static const unsigned int rf_encoded[] = {{
{c_array(encoded)}
}};

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
    for (size_t i = 0; i < {length}u; i++) {{
        unsigned int v = ((unsigned char)candidate[i] + {shift}u) & 0xFFu;
        if (v != rf_encoded[i]) {{
            return 0;
        }}
    }}
    return 1;
}}
"""


def _easy_xor(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    encoded = recipe.constants["encoded"]
    key = recipe.constants["xor_key"]
    length = recipe.constants["flag_length"]
    return f"""static const unsigned int rf_encoded[] = {{
{c_array(encoded)}
}};

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
    for (size_t i = 0; i < {length}u; i++) {{
        unsigned int v = ((unsigned char)candidate[i]) ^ {key}u;
        if (v != rf_encoded[i]) {{
            return 0;
        }}
    }}
    return 1;
}}
"""


def _easy_split(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    parts = recipe.constants["scrambled_chunks"]
    restore = recipe.constants["restore_order"]
    parts_code = ", ".join(c_string(part) for part in parts)
    restore_code = ", ".join(str(v) for v in restore)
    length = recipe.constants["flag_length"]
    return f"""static const char *rf_parts[] = {{ {parts_code} }};
static const unsigned int rf_restore[] = {{ {restore_code} }};

static int {check}(const char *candidate) {{
    char expected[{length + 1}] = {{0}};
    size_t cursor = 0;
    for (size_t i = 0; i < sizeof(rf_restore) / sizeof(rf_restore[0]); i++) {{
        const char *part = rf_parts[rf_restore[i]];
        size_t part_len = strlen(part);
        memcpy(expected + cursor, part, part_len);
        cursor += part_len;
    }}
    expected[cursor] = '\\0';
    return strcmp(candidate, expected) == 0;
}}
"""


def _easy_math(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    adds = recipe.constants["adds"]
    targets = recipe.constants["targets"]
    checksum = recipe.constants["checksum"]
    length = recipe.constants["flag_length"]
    return f"""static const unsigned int rf_adds[] = {{
{c_array(adds)}
}};
static const unsigned int rf_targets[] = {{
{c_array(targets)}
}};

static int {check}(const char *candidate) {{
    unsigned int checksum = 0;
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
    for (size_t i = 0; i < {length}u; i++) {{
        unsigned int b = (unsigned char)candidate[i];
        if ((b + rf_adds[i] + (unsigned int)(i % 7u)) != rf_targets[i]) {{
            return 0;
        }}
        checksum = (checksum + ((unsigned int)i + 3u) * b) & 0xFFFFu;
    }}
    return checksum == {checksum}u;
}}
"""


def _medium_xor_chain(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    encoded = recipe.constants["encoded"]
    k0, k1, k2 = recipe.constants["keys"]
    length = recipe.constants["flag_length"]
    return f"""static const unsigned int rf_encoded[] = {{
{c_array(encoded)}
}};

static int {check}(const char *candidate) {{
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
    for (size_t i = 0; i < {length}u; i++) {{
        unsigned int v = ((unsigned char)candidate[i]) ^ {k0}u;
        v = (v + {k1}u + (unsigned int)i) & 0xFFu;
        v ^= {k2}u;
        if (v != rf_encoded[i]) {{
            return 0;
        }}
    }}
    return 1;
}}
"""


def _medium_chunked_flag(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    length = recipe.constants["flag_length"]
    encoded_chunks = recipe.constants["encoded_chunks"]
    keys = recipe.constants["keys"]
    chunks = recipe.constants["chunks"]
    order = recipe.constants["check_order"]
    functions = []
    calls = []
    offset = 0
    for index, chunk in enumerate(chunks):
        fname = f"{recipe.function_names['stage']}_{index}"
        encoded = encoded_chunks[index]
        functions.append(
            f"""static int {fname}(const char *candidate) {{
    static const unsigned int encoded[] = {{
{c_array(encoded)}
    }};
    for (size_t i = 0; i < {len(chunk)}u; i++) {{
        unsigned int v = ((unsigned char)candidate[{offset}u + i]) ^ {keys[index]}u;
        if (v != encoded[i]) {{
            return 0;
        }}
    }}
    return 1;
}}
"""
        )
        offset += len(chunk)
    for index in order:
        calls.append(f"    if (!{recipe.function_names['stage']}_{index}(candidate)) return 0;")
    return "\n".join(functions) + f"""
static int {check}(const char *candidate) {{
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
{chr(10).join(calls)}
    return 1;
}}
"""


def _medium_arithmetic_validator(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    c = recipe.constants
    length = c["flag_length"]
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
    uint32_t score = 0x811C9DC5u;
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
    for (size_t i = 0; i < {length}u; i++) {{
        unsigned int b = (unsigned char)candidate[i];
        unsigned int v = ((b * rf_muls[i]) + rf_adds[i] + (unsigned int)i) % 257u;
        if (v != rf_targets[i]) {{
            return 0;
        }}
        score = ((score * 33u) ^ (b + rf_targets[i] + (unsigned int)i)) & 0xFFFFFFFFu;
    }}
    return score == {c["score"]}u;
}}
"""


def _hard_state_machine(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    c = recipe.constants
    length = c["flag_length"]
    return f"""static const unsigned int rf_mults[] = {{
{c_array(c["mults"])}
}};
static const unsigned int rf_adds[] = {{
{c_array(c["adds"])}
}};
static const unsigned int rf_states[] = {{
{c_array(c["states"])}
}};

static int {check}(const char *candidate) {{
    unsigned int state = {c["start"]}u;
    unsigned int noise = 0x1357u;
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
    for (size_t i = 0; i < {length}u; i++) {{
        unsigned int b = (unsigned char)candidate[i];
        state = (((state ^ b) * rf_mults[i]) + rf_adds[i]) & 0xFFFFu;
        noise ^= (state << (i % 5u)) | (state >> 3u);
        if ((noise & 0x1Fu) == 0x12u) {{
            noise += b + (unsigned int)i;
        }}
        if (state != rf_states[i]) {{
            return 0;
        }}
    }}
    return 1;
}}
"""


def _hard_multistage(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    c = recipe.constants
    length = c["flag_length"]
    return f"""static unsigned int rf_rotl8(unsigned int value, unsigned int amount) {{
    amount &= 7u;
    return ((value << amount) | (value >> (8u - amount))) & 0xFFu;
}}

static const unsigned int rf_xors[] = {{
{c_array(c["xors"])}
}};
static const unsigned int rf_adds[] = {{
{c_array(c["adds"])}
}};
static const unsigned int rf_rots[] = {{
{c_array(c["rots"])}
}};
static const unsigned int rf_posts[] = {{
{c_array(c["posts"])}
}};
static const unsigned int rf_encoded[] = {{
{c_array(c["encoded"])}
}};

static int {check}(const char *candidate) {{
    unsigned int branch_noise = 0;
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
    for (size_t i = 0; i < {length}u; i++) {{
        unsigned int v = ((unsigned char)candidate[i]) ^ rf_xors[i];
        v = (v + rf_adds[i]) & 0xFFu;
        v = rf_rotl8(v, rf_rots[i]);
        v ^= rf_posts[i];
        branch_noise += (v ^ (unsigned int)i) & 3u;
        if ((branch_noise == 0xFEEDu) && (candidate[i] == 'x')) {{
            return 0;
        }}
        if (v != rf_encoded[i]) {{
            return 0;
        }}
    }}
    return 1;
}}
"""


def _superhard_toy_vm(recipe: ChallengeRecipe) -> str:
    check = recipe.function_names["check"]
    program = recipe.constants["program"]
    length = recipe.constants["flag_length"]
    return f"""static unsigned int rf_vm_rotl8(unsigned int value, unsigned int amount) {{
    amount &= 7u;
    return ((value << amount) | (value >> (8u - amount))) & 0xFFu;
}}

static const unsigned int rf_program[] = {{
{c_array(program)}
}};

static int {check}(const char *candidate) {{
    unsigned int acc = 0;
    size_t pc = 0;
    if (strlen(candidate) != {length}u) {{
        return 0;
    }}
    for (;;) {{
        unsigned int op = rf_program[pc++];
        switch (op) {{
            case 1: {{
                unsigned int index = rf_program[pc++];
                if (index >= {length}u) return 0;
                acc = (unsigned char)candidate[index];
                break;
            }}
            case 2:
                acc = (acc ^ rf_program[pc++]) & 0xFFu;
                break;
            case 3:
                acc = (acc + rf_program[pc++]) & 0xFFu;
                break;
            case 4:
                acc = rf_vm_rotl8(acc, rf_program[pc++]);
                break;
            case 5:
                if (acc != rf_program[pc++]) return 0;
                break;
            case 42:
                acc = (acc + 0x13u) & 0xFFu;
                break;
            case 255:
                return 1;
            default:
                return 0;
        }}
    }}
}}
"""


def _solution_script(recipe: ChallengeRecipe) -> str:
    template = recipe.template_family
    c = recipe.constants
    if template == "baby_plain":
        body = f"flag = {recipe.flag!r}\nprint(flag)\n"
    elif template == "baby_reverse":
        body = f"print({c['reversed_flag']!r}[::-1])\n"
    elif template == "baby_caesar":
        body = f"encoded = {c['encoded']!r}\nshift = {c['shift']!r}\nprint(''.join(chr((b - shift) & 0xff) for b in encoded))\n"
    elif template == "easy_xor":
        body = f"encoded = {c['encoded']!r}\nkey = {c['xor_key']!r}\nprint(''.join(chr(b ^ key) for b in encoded))\n"
    elif template == "easy_split":
        body = f"parts = {c['scrambled_chunks']!r}\norder = {c['restore_order']!r}\nprint(''.join(parts[i] for i in order))\n"
    elif template == "easy_math":
        body = f"targets = {c['targets']!r}\nadds = {c['adds']!r}\nprint(''.join(chr(targets[i] - adds[i] - (i % 7)) for i in range(len(targets))))\n"
    elif template == "medium_xor_chain":
        body = f"""encoded = {c['encoded']!r}
k0, k1, k2 = {tuple(c['keys'])!r}
out = []
for i, value in enumerate(encoded):
    v = value ^ k2
    v = (v - k1 - i) & 0xff
    v ^= k0
    out.append(chr(v))
print(''.join(out))
"""
    elif template == "medium_chunked_flag":
        body = f"""encoded_chunks = {c['encoded_chunks']!r}
keys = {c['keys']!r}
out = []
for chunk, key in zip(encoded_chunks, keys):
    out.extend(chr(b ^ key) for b in chunk)
print(''.join(out))
"""
    elif template == "medium_arithmetic_validator":
        body = f"""muls = {c['muls']!r}
adds = {c['adds']!r}
targets = {c['targets']!r}
out = []
for i, target in enumerate(targets):
    for candidate in range(256):
        if ((candidate * muls[i]) + adds[i] + i) % 257 == target:
            out.append(chr(candidate))
            break
    else:
        raise SystemExit(f'no byte for index {{i}}')
print(''.join(out))
"""
    elif template == "hard_state_machine":
        body = f"""start = {c['start']!r}
mults = {c['mults']!r}
adds = {c['adds']!r}
states = {c['states']!r}
state = start
out = []
for i, wanted in enumerate(states):
    for candidate in range(256):
        next_state = (((state ^ candidate) * mults[i]) + adds[i]) & 0xffff
        if next_state == wanted:
            out.append(chr(candidate))
            state = next_state
            break
    else:
        raise SystemExit(f'no byte for index {{i}}')
print(''.join(out))
"""
    elif template == "hard_multistage":
        body = f"""def ror8(value, amount):
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xff

xors = {c['xors']!r}
adds = {c['adds']!r}
rots = {c['rots']!r}
posts = {c['posts']!r}
encoded = {c['encoded']!r}
out = []
for i, value in enumerate(encoded):
    v = value ^ posts[i]
    v = ror8(v, rots[i])
    v = (v - adds[i]) & 0xff
    v ^= xors[i]
    out.append(chr(v))
print(''.join(out))
"""
    elif template == "superhard_toy_vm":
        body = f"""def ror8(value, amount):
    amount &= 7
    return ((value >> amount) | (value << (8 - amount))) & 0xff

instructions = {c['instructions']!r}
chars = ['?'] * len(instructions)
for item in instructions:
    value = ror8(item['expected'], item['rot'])
    value = (value - item['add']) & 0xff
    value ^= item['xor']
    chars[item['index']] = chr(value)
print(''.join(chars))
"""
    else:
        body = f"print({recipe.flag!r})\n"
    return f"""#!/usr/bin/env python3
# Created by {CREATED_BY}
\"\"\"Solver for this generated RevForge challenge.\"\"\"

{body}"""


def _writeup(recipe: ChallengeRecipe) -> str:
    return f"""# Writeup

Created by {CREATED_BY}

This generated challenge uses the `{recipe.template_family}` template at `{recipe.difficulty}` difficulty.

Recommended approach:

1. Run `file` and `strings` against the binary.
2. Inspect the checker in a disassembler or debugger.
3. Reconstruct the transformation chain listed in `recipe.json`.
4. Confirm the candidate with `./dist/{recipe.name} <flag>`.

The included `solution/solve.py` reconstructs the flag from the generated constants.
"""

