#!/usr/bin/env bash

# Default case for Linux sed, just use "-i"
sedi=(-i)
case "$(uname)" in
  # For macOS, use two parameters
  Darwin*) sedi=(-i "")
esac

# fix math mode (Roam needs two $, Obisidan only 1)
find ./md -name  '*.md' -exec sed "${sedi[@]}" -e 's/\$\$\([^$]\+\)\$\$/$\1$/g' {} \;

# fix italics (Roam uses __x__, Obisian uses *x*)
find ./md -name  '*.md' -exec sed "${sedi[@]}" -e 's/__\([^_]\+\)__/*\1*/g' {} \;
