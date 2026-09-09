# UBCO 2026 vehicle-model paper

LaTeX source for the club technical note that explains `fsae-6dof`, QSS, and the Studio/HUD stack.

```powershell
cd docs/papers
pdflatex ubco-2026-vehicle-model
bibtex ubco-2026-vehicle-model
pdflatex ubco-2026-vehicle-model
pdflatex ubco-2026-vehicle-model
```

Requires a TeX distribution with `article`, `amsmath`, `siunitx`, `hyperref`, `listings`, `booktabs`.
