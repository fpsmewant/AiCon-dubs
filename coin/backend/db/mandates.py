"""Single-user demo mandate, persisted across server restarts."""

from pathlib import Path

from intelligence.generators import UserMandate


PATH = Path(__file__).with_name("mandate.json")


def load_mandate() -> UserMandate | None:
    if not PATH.exists():
        return None
    return UserMandate.model_validate_json(PATH.read_text(encoding="utf-8"))


def save_mandate(mandate: UserMandate) -> UserMandate:
    temp = PATH.with_suffix(".tmp")
    temp.write_text(mandate.model_dump_json(indent=2), encoding="utf-8")
    temp.replace(PATH)
    return mandate
