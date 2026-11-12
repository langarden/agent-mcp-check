# Contributing

- Keep the library zero-dependency (Python 3.9+ stdlib).
- New probes ship with tests; keep them synthetic.
- Server launching must stay subprocess-isolated and time-boxed.
- Trail entries must never contain raw secret payloads.

```bash
pip install -e .
python -m unittest discover -s tests -v
```