# 0.6.1 certification evidence

This directory contains the first schema 2 Windows certification report. It was
captured with mock mode disabled on the same physical Windows 11 machine described
in the compatibility matrix.

Only `tinyllama-1.1b-chat-fp16` on direct CPU is certified by this bundle. The
deterministic context-depth trial constructed an exact 1,536-token prompt using the
model tokenizer, requested one generated token, and recorded three generated tokens.
The requested and actual devices both equal `CPU`.

This is a functional context-capacity result, not a throughput claim. No CPU driver
version is applicable, so the corresponding manifest field is null. GPU, NPU, AUTO,
other models, other context depths, other machines, and performance remain unverified.

The bundle was scanned with `scripts/release_tools.py scan` and manually checked for
usernames, hostnames, email addresses, user-profile paths, Hugging Face tokens, bearer
or API credentials, prompts, generated text, and raw server logs. `SHA256SUMS.txt`
contains the digest of every retained report and this README.
