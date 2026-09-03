from pathlib import Path
import polars as pl

# Project root
ROOT = Path(__file__).resolve().parents[1]

# Source and output folders
SOURCE_DIR = ROOT / "data" / "generated"
OUTPUT_DIR = ROOT / "data" / "generated_csv"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def convert_parquet_files():
    parquet_files = list(SOURCE_DIR.rglob("*.parquet"))

    if not parquet_files:
        print(f"No Parquet files found in: {SOURCE_DIR}")
        return

    print(f"Found {len(parquet_files)} Parquet files\n")

    for parquet_file in parquet_files:
        # Preserve subfolder structure, including sidecar/
        relative_path = parquet_file.relative_to(SOURCE_DIR)

        csv_file = OUTPUT_DIR / relative_path.with_suffix(".csv")

        csv_file.parent.mkdir(parents=True, exist_ok=True)

        print(f"Converting:")
        print(f"  {relative_path}")
        print(f"  → {csv_file.relative_to(ROOT)}")

        df = pl.read_parquet(parquet_file)
        df.write_csv(csv_file)

        print(f"  Rows: {df.height:,} | Columns: {df.width}\n")

    print("=" * 60)
    print("SUCCESS: All Parquet files converted to CSV")
    print(f"Output folder: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    convert_parquet_files()