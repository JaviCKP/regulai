# Cinco puertas después del corrector diagnóstico

Código fijo `972edb88c82a5220a43ffcc89316a9f9033e82f7`; [manifiesto de comandos, códigos, tiempos y hashes](manifest.json). La integración anterior 04 permanece intacta y corresponde al código que hizo el ensayo vivo.

```powershell
rtk proxy .venv/Scripts/python.exe scripts/verify_community.py --output evals/reports/pilot-integrated-gates-20261003-05
```

Todas las puertas terminaron con exit 0: `check`, suite `front api` (**387 pruebas OK en 110,764 s**), `makemigrations --check --dry-run`, evaluación offline de 150 recorridos y auditorías de aplicación/laboratorio PostgreSQL. [Log completo](front-api.log). `source_unchanged=true` y `passed=true`.

No hay migraciones pendientes ni vulnerabilidades conocidas en los paquetes auditables. El modelo `xx-ent-wiki-sm` queda fuera de pip-audit por no estar en PyPI; se verifica su identidad por separado. Cero llamadas pagadas de producto durante estas comprobaciones. No se ejecutó CI remoto.

El corrector conserva códigos seguros de Jev, sus reservas y el resultado incierto; no cambia modelos, umbrales ni etiquetas. Esta ejecución nueva está justificada por el cambio de código posterior al ensayo; los siguientes cambios solo documentales no requieren repetir la suite.
