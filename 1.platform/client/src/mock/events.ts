import type { MissionEvent } from "../lib/types";
import { MODEL_NANO, MODEL_SUPER, MODEL_ULTRA } from "./fixtures";

type DistributiveOmit<T, K extends keyof T> = T extends unknown
  ? Omit<T, K>
  : never;

/** An event with its `id` still to be assigned by position. */
export type MockFrame = DistributiveOmit<MissionEvent, "id">;

const out = (attempt: string, line: string): MockFrame => ({
  name: "terminal",
  data: { attempt, stream: "stdout", line },
});

const err = (attempt: string, line: string): MockFrame => ({
  name: "terminal",
  data: { attempt, stream: "stderr", line },
});

const cmd = (attempt: string, line: string): MockFrame => ({
  name: "terminal",
  data: { attempt, stream: "cmd", line },
});

export const MOCK_FRAMES: MockFrame[] = [
  { name: "status", data: { status: "PENDING", iteration: 0 } },
  { name: "status", data: { status: "PROVISIONING", iteration: 0 } },
  cmd("baseline", "git clone --depth 50 https://github.com/archon-demo/billing-api /w"),
  out("baseline", "Cloning into '/w'..."),
  out("baseline", "remote: Enumerating objects: 412, done."),
  out("baseline", "Resolving deltas: 100% (198/198), done."),
  cmd("baseline", "cd /w && pip install -e '.[dev]'"),
  out("baseline", "Successfully installed billing-api-2.1.0 pydantic-2.9.2"),

  { name: "status", data: { status: "REPRODUCING", iteration: 0 } },
  cmd("baseline", "cd /w && pytest tests/ -q"),
  err("baseline", "ImportError while loading conftest '/w/tests/conftest.py'."),
  err("baseline", "app/schemas/user.py:3: in <module>"),
  err("baseline", "    from pydantic import BaseModel, validator"),
  err(
    "baseline",
    "E   PydanticImportError: `validator` has been removed in V2. Use `field_validator`.",
  ),
  out("baseline", "18 errors in 0.94s"),
  {
    name: "tests",
    data: {
      attempt: "baseline",
      exit_code: 2,
      fail_to_pass: 0,
      pass_to_pass_broken: 0,
      total: 18,
    },
  },

  { name: "status", data: { status: "GROUNDING", iteration: 1 } },
  {
    name: "thought",
    data: {
      stage: "GROUNDING",
      model: MODEL_SUPER,
      text: "The suite never reaches a test — collection dies at import. `PydanticImportError` names the exact symbol, so this is a v1 API that was deleted in v2 rather than a behavioural regression. Checking the upstream migration guide before writing anything.",
    },
  },
  {
    name: "tavily",
    data: {
      query: "pydantic v2 validator removed use field_validator migration classmethod",
      results: 5,
      ms: 812,
    },
  },

  { name: "status", data: { status: "REASONING", iteration: 1 } },
  {
    name: "thought",
    data: {
      stage: "REASONING",
      model: MODEL_ULTRA,
      text: "Root cause: `app/schemas/user.py` and `app/schemas/invoice.py` still import `validator` from pydantic, removed in 2.0. The replacement is `field_validator`, which — unlike the v1 decorator — does not implicitly bind the function as a classmethod. Candidate 1 swaps the import and the decorator name only. Candidate 2 additionally stacks `@classmethod` under each `@field_validator`.",
    },
  },
  {
    name: "usage",
    data: {
      model: MODEL_ULTRA,
      prompt_tokens: 61_234,
      completion_tokens: 2_210,
      cost_usd: 0.181,
    },
  },

  { name: "status", data: { status: "TESTING", iteration: 1 } },
  {
    name: "patch",
    data: {
      attempt: "a_01",
      files: [{ path: "app/schemas/user.py", added: 4, removed: 4 }],
    },
  },
  cmd("a_01", "git apply --check /tmp/a_01.patch && pytest tests/ -q"),
  out("a_01", "collected 18 items"),
  err("a_01", "FAILED tests/test_user.py::test_email_lowercase - TypeError: 'classmethod' object is not callable"),
  err("a_01", "FAILED tests/test_user.py::test_signup_date_guard - TypeError"),
  out("a_01", "15 passed, 3 failed in 1.62s"),
  {
    name: "tests",
    data: {
      attempt: "a_01",
      exit_code: 1,
      fail_to_pass: 1,
      pass_to_pass_broken: 2,
      total: 18,
    },
  },
  {
    name: "thought",
    data: {
      stage: "TESTING",
      model: MODEL_NANO,
      text: "a_01: 15 passed, 3 failed. Import error cleared, but two previously passing validator tests now raise TypeError on the bare function object.",
    },
  },
  {
    name: "usage",
    data: {
      model: MODEL_NANO,
      prompt_tokens: 12_040,
      completion_tokens: 430,
      cost_usd: 0.006,
    },
  },

  { name: "status", data: { status: "REASONING", iteration: 2 } },
  {
    name: "thought",
    data: {
      stage: "REASONING",
      model: MODEL_ULTRA,
      text: "Confirmed: `field_validator` requires an explicit `@classmethod` beneath it. Also `Invoice.Config.allow_mutation = False` has no v2 equivalent — it must become `model_config = ConfigDict(frozen=True)`. Emitting two candidates in parallel: a_02 is the minimal decorator + config fix, a_03 additionally rewrites the schemas onto `Annotated` field constraints.",
    },
  },
  {
    name: "usage",
    data: {
      model: MODEL_ULTRA,
      prompt_tokens: 57_186,
      completion_tokens: 2_100,
      cost_usd: 0.150,
    },
  },

  { name: "status", data: { status: "TESTING", iteration: 2 } },
  {
    name: "patch",
    data: {
      attempt: "a_02",
      files: [
        { path: "app/schemas/user.py", added: 6, removed: 4 },
        { path: "app/schemas/invoice.py", added: 8, removed: 6 },
      ],
    },
  },
  {
    name: "patch",
    data: {
      attempt: "a_03",
      files: [
        { path: "app/schemas/user.py", added: 14, removed: 10 },
        { path: "app/schemas/invoice.py", added: 17, removed: 12 },
      ],
    },
  },
  cmd("a_02", "git apply --check /tmp/a_02.patch && pytest tests/ -q"),
  cmd("a_03", "git apply --check /tmp/a_03.patch && pytest tests/ -q"),
  out("a_02", "collected 18 items"),
  out("a_03", "collected 18 items"),
  out("a_02", "tests/test_user.py ......                    [ 33%]"),
  err("a_03", "FAILED tests/test_invoice.py::test_currency_default - ValidationError"),
  out("a_02", "tests/test_invoice.py ............            [100%]"),
  out("a_02", "18 passed in 1.71s"),
  out("a_03", "17 passed, 1 failed in 1.88s"),
  {
    name: "tests",
    data: {
      attempt: "a_02",
      exit_code: 0,
      fail_to_pass: 3,
      pass_to_pass_broken: 0,
      total: 18,
    },
  },
  {
    name: "tests",
    data: {
      attempt: "a_03",
      exit_code: 1,
      fail_to_pass: 3,
      pass_to_pass_broken: 1,
      total: 18,
    },
  },

  { name: "status", data: { status: "REVIEWING", iteration: 2 } },
  {
    name: "thought",
    data: {
      stage: "REVIEWING",
      model: MODEL_SUPER,
      text: "a_02 is the only candidate with zero regressions and it is also the smaller diff (14 lines vs 31). Checking it for deleted tests, writes outside the repository, and credential-shaped strings before approving.",
    },
  },
  {
    name: "review",
    data: {
      attempt: "a_03",
      verdict: "REJECT",
      reasons: [
        "Breaks tests/test_invoice.py::test_currency_default",
        "Rewrites field declarations beyond the scope of the failure",
      ],
    },
  },
  {
    name: "review",
    data: {
      attempt: "a_02",
      verdict: "APPROVE",
      reasons: [
        "3 fail-to-pass, 0 pass-to-pass broken",
        "Touches only the two modules named in the traceback",
        "No test files removed or weakened",
      ],
    },
  },
  {
    name: "usage",
    data: {
      model: MODEL_SUPER,
      prompt_tokens: 41_980,
      completion_tokens: 1_870,
      cost_usd: 0.068,
    },
  },

  { name: "status", data: { status: "VERIFIED", iteration: 2 } },
  {
    name: "done",
    data: {
      status: "VERIFIED",
      selected_attempt: "a_02",
      iterations: 2,
      spend_usd: 0.412,
    },
  },
];
