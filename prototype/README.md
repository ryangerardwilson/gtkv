# Block Prototype

This is a GTK4-only prototype for a block-based editor that separates text and
image blocks. The goal is to explore a layout where inline images are removed
and text blocks can be backed by a Vim engine later.

## Run

```bash
python prototype/main.py
```

Optional image:

```bash
python prototype/main.py --image /path/to/image.png
```

Or:

```bash
GTKV_PROTO_IMAGE=/path/to/image.png python prototype/main.py
```

## Shortcuts

- `Ctrl+V`: append a new text (Vim) block
- `Ctrl+I`: launch the `o` picker and append an image block
