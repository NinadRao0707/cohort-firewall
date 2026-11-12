# Synthea data (optional, engine testing only)

Synthea is MITRE's open-source synthetic patient generator. We used it to check the readiness engine on
a second data source. **It is not used for judged results**, and no generated files are committed.

## Requirements
Java 17 or newer (`java -version`). On macOS with Homebrew: `brew install openjdk@17`, then follow the
linking instructions Homebrew prints.

## 1. Download Synthea
Download `synthea-with-dependencies.jar` from the releases page of
https://github.com/synthetichealth/synthea into a folder outside this repository, such as `~/synthea`.

## 2. Generate a breast cancer population
```bash
cd ~/synthea
java -jar synthea-with-dependencies.jar -s 20261115 -p 35000 -g F -a 40-85 \
  -m breast_cancer --exporter.csv.export true --exporter.fhir.export false \
  --exporter.baseDirectory ./output_large/ Massachusetts
```
- `-s` fixes the seed, so everyone gets the same data.
- If `-m breast_cancer` doesn't match your Synthea version's module name, leave it out; the flattener filters for breast cancer anyway.

## 3. Inspect, flatten and check
```bash
cd ~/cohort-firewall && source .venv/bin/activate
python data/flatten_synthea.py --synthea-dir ~/synthea/output_large/csv --cancer breast --inspect-values
python data/flatten_synthea.py --synthea-dir ~/synthea/output_large/csv --cancer breast --out data/synthea_large
python scripts/run_synthea_specs.py --data-dir data/synthea_large
```
`data/synthea*/` is git-ignored. Confirm the license that applies to your Synthea output before citing it.
