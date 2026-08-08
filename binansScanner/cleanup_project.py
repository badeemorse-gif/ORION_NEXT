from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).parent

# امتدادات الملفات التي سيتم تنظيفها
TARGET_EXTENSIONS = {".py"}

# أنماط يجب حذفها بالكامل إذا ظهرت في سطر منفصل
REMOVE_PATTERNS = [
    re.compile(r"^\s*```.*$"),                # ``` أو ```python
    re.compile(r"^\s*~~~.*$"),                # ~~~
    re.compile(r"^\s*\*\*\*+\s*$"),          # ***
    re.compile(r"^\s*---+\s*$"),             # ---
    re.compile(r"^\s*###.*$"),               # ### Heading
]

# حذف أجزاء مثل داخل أي سطر
CITE_PATTERN = re.compile(r"\s*\[cite:\s*\d+\]")

removed_lines = 0
cleaned_files = []


def should_skip(path: Path) -> bool:
    parts = set(path.parts)

    # تجاهل البيئات والمجلدات غير المهمة
    ignored = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        ".idea",
        ".vscode",
    }

    return bool(parts & ignored)


for file in PROJECT_ROOT.rglob("*"):

    if not file.is_file():
        continue

    if file.suffix not in TARGET_EXTENSIONS:
        continue

    if should_skip(file):
        continue

    try:
        original = file.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        continue

    new_lines = []

    changed = False

    for line in original:

        # إزالة [cite: xx]
        cleaned = CITE_PATTERN.sub("", line)

        # حذف أسطر markdown
        if any(p.match(cleaned) for p in REMOVE_PATTERNS):
            removed_lines += 1
            changed = True
            continue

        # إزالة السطر إذا أصبح فارغًا بعد حذف cite وكان أصله مجرد cite
        if cleaned.strip() == "" and "[cite:" in line:
            removed_lines += 1
            changed = True
            continue

        if cleaned != line:
            changed = True

        new_lines.append(cleaned.rstrip())

    if changed:
        file.write_text(
            "\n".join(new_lines) + "\n",
            encoding="utf-8",
        )
        cleaned_files.append(file.relative_to(PROJECT_ROOT))

for f in cleaned_files:
    print(f"CLEANED : {f}")

print()
print("=" * 60)
print(f"Removed Lines : {removed_lines}")
print("PROJECT CLEANUP COMPLETED")
print("=" * 60)
