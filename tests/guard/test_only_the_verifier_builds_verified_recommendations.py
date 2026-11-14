import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
ALLOWED = SRC / "hybrid_fraud" / "guard" / "verifier.py"


def _builds_verified(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            f = node.func
            # Catches VerifiedRecommendation(...) and VerifiedRecommendation.model_validate(...).
            target = f.value if isinstance(f, ast.Attribute) else f
            if getattr(target, "id", "") == "VerifiedRecommendation":
                return True
    return False


def test_nothing_outside_the_verifier_constructs_a_verified_recommendation():
    offenders = [
        str(p.relative_to(SRC))
        for p in SRC.rglob("*.py")
        if p != ALLOWED and _builds_verified(ast.parse(p.read_text(encoding="utf-8")))
    ]
    assert offenders == []
