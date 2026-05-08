#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

import onnx


def analyze_model(model_path: str):
    path = Path(model_path)
    if not path.exists():
        print(f"[SKIP] File not found: {model_path}", file=sys.stderr)
        return

    try:
        model = onnx.load(str(path))
        onnx.checker.check_model(model)
    except onnx.checker.ValidationError as e:
        print(f"[{path.name}] INVALID: {e}", file=sys.stderr)
        return
    except Exception as e:
        print(f"[{path.name}] Failed to load: {e}", file=sys.stderr)
        return

    g = model.graph

    print(f"\n{'='*60}")
    print(f"Model: {path.name}")
    print(f"Path:  {path.resolve()}")
    print(f"{'='*60}")

    # ModelProto metadata
    print(f"IrVersion:  {model.ir_version}")
    print(f"Producer:   {model.producer_name}")
    print(f"Version:    {model.model_version}")
    print(f"DocString:  {model.doc_string}")

    # Inputs
    print(f"\n--- Inputs ({len(g.input)}) ---")
    for i, inp in enumerate(g.input):
        shape = [d.dim_value if d.dim_value else -1 for d in inp.type.tensor_type.shape.dim]
        print(f"  [{i}] Name:  {inp.name}")
        print(f"      Shape: {shape}")
        print(f"      Type:  {onnx.TensorProto.DataType.Name(inp.type.tensor_type.elem_type)}")

    # Outputs
    print(f"\n--- Outputs ({len(g.output)}) ---")
    for i, out in enumerate(g.output):
        shape = [d.dim_value if d.dim_value else -1 for d in out.type.tensor_type.shape.dim]
        print(f"  [{i}] Name:  {out.name}")
        print(f"      Shape: {shape}")
        print(f"      Type:  {onnx.TensorProto.DataType.Name(out.type.tensor_type.elem_type)}")

    # Graph info
    print(f"\n--- Graph ---")
    print(f"  Nodes:        {len(g.node)}")
    ops = {}
    for n in g.node:
        key = f"{n.domain}/{n.op_type}" if n.domain else n.op_type
        ops[key] = ops.get(key, 0) + 1
    print(f"  Ops:")
    for op, cnt in sorted(ops.items(), key=lambda x: -x[1]):
        print(f"    {op}: {cnt}")

    # Initializers (weights)
    print(f"  Initializers: {len(g.initializer)}")
    total_params = 0
    for init in g.initializer:
        n_elems = 1
        for d in init.dims:
            n_elems *= d
        total_params += n_elems
    print(f"  Total param elements: {total_params:,}")


def main():
    parser = argparse.ArgumentParser(
        description="Inspect ONNX model files and print input/output shapes and metadata."
    )
    parser.add_argument(
        "path", nargs="?",
        help="Path to a single .onnx file or a root directory to scan recursively"
    )
    parser.add_argument(
        "--no-recursive", action="store_false", dest="recursive",
        help="Do not scan subdirectories"
    )
    args = parser.parse_args()

    target = Path(args.path) if args.path else Path.cwd()

    if target.is_file():
        if target.suffix.lower() == ".onnx":
            analyze_model(str(target))
        else:
            print(f"Not an .onnx file: {target}", file=sys.stderr)
            sys.exit(1)
    elif target.is_dir():
        pattern = "**/*.onnx" if args.recursive else "*.onnx"
        files = sorted(target.glob(pattern))
        if not files:
            print(f"No .onnx files found in {target}", file=sys.stderr)
            return
        for f in files:
            analyze_model(str(f))
    else:
        print(f"Path does not exist: {target}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
