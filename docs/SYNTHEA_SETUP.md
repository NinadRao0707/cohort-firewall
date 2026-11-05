# Generating Synthea breast cancer data

Synthea is MITRE's open-source synthetic patient generator. It needs Java (JDK 17 or newer is a
safe choice; check the Synthea README for the current requirement).

## 1. Get Synthea
Download `synthea-with-dependencies.jar` from the Releases page of
https://github.com/synthetichealth/synthea, into a folder outside this repo (for example `~/synthea`).

## 2. Generate a population with CSV export
CSV export is off by default, so turn it on. Breast cancer is rare in a general population, so
generate women in an older age range and plenty of them; the flattener keeps only cancer patients.

```bash
cd ~/synthea
java -jar synthea-with-dependencies.jar -s 20261114 -p 5000 -g F -a 40-85 \
  -m breast_cancer --exporter.csv.export true --exporter.fhir.export false Massachusetts
```

- `-m breast_cancer` limits modules. Check the module's exact name in the Synthea Module Gallery
  (wiki) or under `src/main/resources/modules/`; if it doesn't match, drop `-m` and rely on the
  flattener's filter instead.
- `-s` fixes the seed so the whole team gets the same data.
- Output lands in `./output/csv/` (patients.csv, conditions.csv, observations.csv, ...).
- The Synthea wiki's "CSV File Data Dictionary" page documents every column.

## 3. Inspect, then map fields
```bash
cd <repo>
python data/flatten_synthea.py --synthea-dir ~/synthea/output/csv --cancer breast --inspect
```
Share the printed condition and observation descriptions. They decide what goes into
`FEATURE_KEYWORDS` (receptor status, tumor size, stage) and whether recurrence exists as a
condition or must be replaced by death as the outcome.

## 4. Flatten and evaluate
```bash
python data/flatten_synthea.py --synthea-dir ~/synthea/output/csv --cancer breast --out data/synthea
```
`data/synthea/` is git-ignored. Commit the command and seed, not the generated files.
Confirm the license that applies to Synthea output before stating it in the dictionary.
