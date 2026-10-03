# Cinco puertas finales tras añadir Vercel

Código `698e8f0bb11b6f5ef91e8ac27ef9404c8868f7cc`, fuentes sin cambios durante la ejecución. [Manifiesto de comandos, códigos y hashes](manifest.json).

```powershell
rtk proxy .venv/Scripts/python.exe scripts/verify_community.py --output evals/reports/pilot-integrated-gates-20261003-04
```

- `check`: exit 0.
- Suite `front api`: **382 pruebas OK en 162,656 s**, exit 0; [log completo](front-api.log).
- `makemigrations --check --dry-run`: exit 0, sin migraciones pendientes.
- Evaluación offline: **150 recorridos, cero controles fallidos**, exit 0. Los fallos simulados que aparecen dentro del log de tests son fixtures de sus regresiones, no el resultado de este gate separado.
- Auditorías de dependencias de aplicación y laboratorio PostgreSQL: exit 0, sin vulnerabilidades conocidas entre los paquetes auditables. `xx-ent-wiki-sm` no figura en PyPI y queda fuera de la auditoría; su artefacto e identidad se verifican por separado.

`source_unchanged=true`, `passed=true`. Cero llamadas pagadas de producto. Validación local del workflow; no se ejecutó CI remoto. Los paquetes01–03 anteriores conservan sus resultados originales. Las suites parciales se solapan y no se suman a estas 382 pruebas.
