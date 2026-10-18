# Resumen de resultados

## Parámetros de la corrida

- **Capacidad inicial C0 [MWh]**: 1,120
- **Cédula**: 001 036 450 633
- **Horizonte [h]**: 24
- **Paso del barrido [MWh]**: 250.0
- **Tolerancia [MWh]**: 10.0
- **Objetivo [fracción de FO base]**: 0.5
- **MIP gap barrido / red**: 0.0001 / 0.0001
- **Límite de carga**: pc (corregido)
- **Potencia escalada con la capacidad**: True
- **SOC final >= inicial**: True
- **Penalización vertimiento [$/MWh]**: 10,000
- **VOLL [$/MWh]**: 500,000

## 2.1 Capacidad instalada vs función objetivo

- FO sin baterías: **43,531,806 $**
- Objetivo (50 %): **21,765,903 $**
- Capacidad que cumple el objetivo: **4,127.8 MWh** (FO = 21,748,892 $, 49.96 % de la base)

| Capacidad [MWh] | FO [$] | FO / FO base | Vertimiento [MWh] | Carga [MWh] | Descarga [MWh] | dFO/dC [$/MWh] |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 43,531,806 | 100.00 % | 4,324.5 | 0.0 | 0.0 |  |
| 1,120.0 | 36,133,368 | 83.00 % | 3,585.3 | 1,421.4 | 579.9 | -6,606 |
| 1,370.0 | 34,589,498 | 79.46 % | 3,431.0 | 1,887.0 | 806.1 | -6,175 |
| 1,620.0 | 33,212,439 | 76.29 % | 3,293.5 | 2,040.1 | 836.5 | -5,508 |
| 1,870.0 | 31,836,432 | 73.13 % | 3,156.0 | 2,306.4 | 935.2 | -5,504 |
| 2,120.0 | 30,585,911 | 70.26 % | 3,031.0 | 2,506.5 | 997.0 | -5,002 |
| 2,370.0 | 29,486,096 | 67.73 % | 2,921.0 | 2,810.6 | 1,140.1 | -4,399 |
| 2,620.0 | 28,385,567 | 65.21 % | 2,811.0 | 2,973.1 | 1,193.7 | -4,402 |
| 2,870.0 | 27,284,937 | 62.68 % | 2,701.0 | 3,137.8 | 1,253.1 | -4,403 |
| 3,120.0 | 26,184,340 | 60.15 % | 2,591.0 | 3,295.0 | 1,303.7 | -4,402 |
| 3,370.0 | 25,084,400 | 57.62 % | 2,481.0 | 3,465.3 | 1,372.1 | -4,400 |
| 3,620.0 | 23,983,961 | 55.10 % | 2,371.0 | 3,627.8 | 1,427.6 | -4,402 |
| 3,870.0 | 22,883,643 | 52.57 % | 2,261.0 | 3,780.7 | 1,472.5 | -4,401 |
| 4,120.0 | 21,783,274 | 50.04 % | 2,151.0 | 3,759.4 | 1,381.3 | -4,401 |
| 4,127.8 | 21,748,892 | 49.96 % | 2,147.6 | 3,763.2 | 1,382.0 | -4,401 |
| 4,135.6 | 21,714,510 | 49.88 % | 2,144.2 | 3,767.0 | 1,382.7 | -4,401 |
| 4,151.2 | 21,645,746 | 49.72 % | 2,137.3 | 3,774.5 | 1,384.2 | -4,401 |
| 4,182.5 | 21,508,218 | 49.41 % | 2,123.5 | 3,789.6 | 1,387.1 | -4,401 |
| 4,245.0 | 21,232,061 | 48.77 % | 2,096.0 | 3,828.6 | 1,401.4 | -4,419 |
| 4,370.0 | 20,681,944 | 47.51 % | 2,041.0 | 3,900.4 | 1,425.0 | -4,401 |

## 2.2 Demanda original vs demanda con baterías

- Capacidad: 4,127.8 MWh
- Energía cargada: 3,763.2 MWh | descargada: 1,382.0 MWh
- Horas con carga > 0: 21 | con descarga > 0: 10
- Pico de demanda original: 2,513.2 MW | con baterías: 2,741.1 MW
- Vertimiento sin baterías: 4,324.5 MWh | con baterías: 2,147.6 MWh
- Energía almacenada al inicio: 1,356.1 MWh | al final: 2,062.1 MWh
- Baterías-hora con carga y descarga simultánea (diagnóstico): 0

## 2.3 Con y sin red

| Caso | FO [$] | Vertimiento [MWh] | Carga máx. línea [%] | Líneas-hora congestionadas |
|---|---:|---:|---:|---:|
| con red, sin BESS | 43,531,805.56 | 4,324.5 | 92.2 | 0 |
| sin red, sin BESS | 43,531,748.09 | 4,324.5 | — | — |
| con red, BESS 4,128 MWh | 21,748,892.33 | 2,147.6 | 89.7 | 0 |
| sin red, BESS 4,128 MWh | 21,748,242.22 | 2,147.6 | — | — |

- Sin baterías: FO(con red) − FO(sin red) = **57.48 $** (0.00013 %)
- Con baterías: FO(con red) − FO(sin red) = **650.11 $** (0.00299 %)
