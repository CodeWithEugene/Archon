# Expected fix: migrate `userkit` from Pydantic V1 to V2

## Baseline (as committed)

```
pytest -q  ->  4 failed, 2 passed
```

Failing tests:

- `tests/test_schemas.py::test_user_to_dict_uses_v2_serialization`
- `tests/test_schemas.py::test_parse_user_uses_v2_validation`
- `tests/test_schemas.py::test_user_from_row_reads_attributes`
- `tests/test_schemas.py::test_model_declares_v2_config_and_validators`

Passing tests (must stay passing): `test_email_is_normalized`,
`test_invalid_email_is_rejected`.

## Root cause

`userkit/schemas.py` and `userkit/service.py` are written against the Pydantic
V1 API. Under `pydantic>=2` these paths either emit
`PydanticDeprecatedSince20` or fail outright:

| V1 construct | V2 behaviour |
| --- | --- |
| `@validator("email")` | Deprecation warning; validator runs through a shim |
| `class Config: orm_mode = True` | Deprecation warning; `orm_mode` is silently dropped (renamed to `from_attributes`) |
| `User.from_orm(row)` | **Hard error** — `PydanticUserError: You must set the config attribute 'from_attributes=True' to use from_orm` |
| `user.dict()` | Deprecation warning; use `model_dump()` |
| `User.parse_obj(payload)` | Deprecation warning; use `model_validate()` |

Because `orm_mode` is not a valid V2 config key it never reaches the model
config, so `from_orm` raises even though the author declared it.

## Required changes

### 1. `userkit/schemas.py` — validators

Replace the V1 import and decorators:

```python
from pydantic import BaseModel, ConfigDict, field_validator


@field_validator("email")
@classmethod
def normalize_email(cls, value: str) -> str: ...
```

`@field_validator` must be stacked **above** `@classmethod`, and the method
must take `cls` explicitly. The validation logic itself is unchanged, so the
two behavioural tests keep passing.

### 2. `userkit/schemas.py` — model config

Replace the inner `Config` class with a `model_config` assignment:

```python
model_config = ConfigDict(from_attributes=True)
```

Class-based `Config` is deprecated in V2, and `orm_mode` must be renamed to
`from_attributes`. Place `model_config` at the top of the class body, before
the field declarations.

### 3. `userkit/service.py` — serialization and parsing

| Before | After |
| --- | --- |
| `user.dict()` | `user.model_dump()` |
| `User.parse_obj(payload)` | `User.model_validate(payload)` |
| `User.from_orm(row)` | `User.model_validate(row)` |

`model_validate` handles both mappings and attribute-carrying objects once
`from_attributes=True` is set on the model, so `from_orm` has no replacement
call of its own — it collapses into `model_validate`.

## Expected result after the fix

```
pytest -q  ->  6 passed
```

No `PydanticDeprecatedSince20` warnings should remain: the tests assert this
by promoting `DeprecationWarning` to an error around each call.

A complete reference fix is provided in `solution.patch`:

```bash
git apply solution.patch && ./test.sh
```
