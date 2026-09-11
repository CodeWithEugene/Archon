/**
 * Canned mission used when `NEXT_PUBLIC_ARCHON_MOCK=1`.
 *
 * Scenario: a pydantic v1 -> v2 breakage. Two `@validator` decorators survived
 * the dependency bump; the suite dies on import. ARCHON needs two iterations —
 * the first attempt drops the `@classmethod` wrapper and breaks two passing
 * tests, the second iteration runs two candidates in parallel and one is
 * approved.
 */

import type {
  DiffFile,
  Health,
  Mission,
  ReplaySummary,
  SweInstance,
} from "../lib/types";

export const MOCK_MISSION_ID = "m_9c41ab";
export const MOCK_REPO = "https://github.com/archon-demo/billing-api";

export const MODEL_ULTRA = "nvidia/nemotron-3-ultra-550b-a55b";
export const MODEL_SUPER = "nvidia/nemotron-3-super-120b-a12b";
export const MODEL_NANO = "nvidia/nemotron-3-nano-30b-a3b";

export const mockHealthPayload: Health = {
  ok: true,
  sandbox_backend: "mock (in-browser)",
  models: { ultra: MODEL_ULTRA, super: MODEL_SUPER, nano: MODEL_NANO },
};

export const mockSweInstancesPayload: SweInstance[] = [
  {
    id: "pydantic__pydantic-8567",
    repo: "pydantic/pydantic",
    short_problem: "field_validator loses the classmethod binding on inherited models",
  },
  {
    id: "django__django-16873",
    repo: "django/django",
    short_problem: "join filter crashes when autoescape is off and the list is empty",
  },
  {
    id: "sympy__sympy-24152",
    repo: "sympy/sympy",
    short_problem: "TensorProduct.expand ignores the scalar factor of a summand",
  },
  {
    id: "requests__requests-6028",
    repo: "psf/requests",
    short_problem: "proxy authentication header dropped on Python 3.8.12",
  },
];

export const mockReplaysPayload: ReplaySummary[] = [
  {
    id: "golden_pydantic_v2",
    title: "pydantic v2 — field_validator migration",
    type: "BUG_HEALING",
    repo_url: MOCK_REPO,
    swe_instance_id: null,
    status: "VERIFIED",
    iterations: 2,
    resolved: true,
    duration_s: 184,
  },
  {
    id: "golden_django_16873",
    title: "django — empty join filter with autoescape off",
    type: "BUG_HEALING",
    repo_url: null,
    swe_instance_id: "django__django-16873",
    status: "VERIFIED",
    iterations: 1,
    resolved: true,
    duration_s: 96,
  },
  {
    id: "golden_flask_migration",
    title: "flask 2 -> 3 — before_first_request removal",
    type: "MIGRATION",
    repo_url: "https://github.com/archon-demo/orders-svc",
    swe_instance_id: null,
    status: "FAILED",
    iterations: 5,
    resolved: false,
    duration_s: 412,
  },
];

const USER_ORIGINAL = `from datetime import date

from pydantic import BaseModel, validator


class User(BaseModel):
    id: int
    email: str
    signup_date: date

    @validator("email")
    def email_must_be_lowercase(cls, value: str) -> str:
        if value != value.lower():
            raise ValueError("email must be lowercase")
        return value

    @validator("signup_date")
    def not_in_the_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("signup_date cannot be in the future")
        return value
`;

const USER_MODIFIED = `from datetime import date

from pydantic import BaseModel, field_validator


class User(BaseModel):
    id: int
    email: str
    signup_date: date

    @field_validator("email")
    @classmethod
    def email_must_be_lowercase(cls, value: str) -> str:
        if value != value.lower():
            raise ValueError("email must be lowercase")
        return value

    @field_validator("signup_date")
    @classmethod
    def not_in_the_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("signup_date cannot be in the future")
        return value
`;

const INVOICE_ORIGINAL = `from decimal import Decimal

from pydantic import BaseModel, validator


class Invoice(BaseModel):
    number: str
    amount: Decimal
    currency: str = "USD"

    @validator("amount")
    def amount_is_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be positive")
        return value

    class Config:
        allow_mutation = False
`;

const INVOICE_MODIFIED = `from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator


class Invoice(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: str
    amount: Decimal
    currency: str = "USD"

    @field_validator("amount")
    @classmethod
    def amount_is_positive(cls, value: Decimal) -> Decimal:
        if value <= 0:
            raise ValueError("amount must be positive")
        return value
`;

export const mockDiffPayload: DiffFile[] = [
  {
    path: "app/schemas/user.py",
    original: USER_ORIGINAL,
    modified: USER_MODIFIED,
    language: "python",
  },
  {
    path: "app/schemas/invoice.py",
    original: INVOICE_ORIGINAL,
    modified: INVOICE_MODIFIED,
    language: "python",
  },
];

const SELECTED_PATCH = `diff --git a/app/schemas/user.py b/app/schemas/user.py
--- a/app/schemas/user.py
+++ b/app/schemas/user.py
@@
-from pydantic import BaseModel, validator
+from pydantic import BaseModel, field_validator
`;

/** Mission record as returned before the stream has produced anything. */
export function mockMissionInitial(id: string): Mission {
  return {
    id,
    type: "BUG_HEALING",
    repo_url: MOCK_REPO,
    git_ref: "main",
    test_command: "pytest tests/ -q",
    swe_instance_id: null,
    status: "PENDING",
    iteration: 0,
    spend_usd: 0,
    created_at: new Date().toISOString(),
    attempts: [],
    usage: [],
  };
}

/** Mission record after the canned run has finished. */
export function mockMissionFinal(id: string): Mission {
  return {
    ...mockMissionInitial(id),
    status: "VERIFIED",
    iteration: 2,
    spend_usd: 0.412,
    attempts: [
      {
        id: "a_01",
        iteration: 1,
        exit_code: 1,
        fail_to_pass: 1,
        pass_to_pass_broken: 2,
        patch_lines: 8,
        selected: false,
        patch: SELECTED_PATCH,
      },
      {
        id: "a_02",
        iteration: 2,
        exit_code: 0,
        fail_to_pass: 3,
        pass_to_pass_broken: 0,
        patch_lines: 14,
        selected: true,
        patch: SELECTED_PATCH,
      },
      {
        id: "a_03",
        iteration: 2,
        exit_code: 1,
        fail_to_pass: 3,
        pass_to_pass_broken: 1,
        patch_lines: 31,
        selected: false,
        patch: SELECTED_PATCH,
      },
    ],
    usage: [
      {
        model: MODEL_ULTRA,
        prompt_tokens: 118_420,
        completion_tokens: 4_310,
        cost_usd: 0.331,
      },
      {
        model: MODEL_SUPER,
        prompt_tokens: 41_980,
        completion_tokens: 1_870,
        cost_usd: 0.068,
      },
      {
        model: MODEL_NANO,
        prompt_tokens: 22_640,
        completion_tokens: 940,
        cost_usd: 0.013,
      },
    ],
  };
}
