# Amazon price tracker

Searches Amazon Germany within the configured price range, reads product details, and writes a cheapest-item JSON report.

## Setup and execution

Use Python 3.11 and a separate virtual environment for this project. Run commands from this folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python check_inputs.py
python simple_tracker.py --search "PS4" --output-dir reports
```

On Windows, activate with `.venv\Scripts\activate`. For notebooks, select this environment’s kernel and execute from the top in a fresh kernel. The first code cell exposes `INPUT_PATHS` where old machine-specific paths existed. `PROJECT_DATA_DIR` changes the base for those configured paths; remaining relative paths use the notebook working directory.

## Inputs

No fixed external dataset is required for the default entry point. See the notes below for bundled files or command-line input requirements.

## Outputs

reports/<search>.json with product URLs, prices, filter settings, and the cheapest item.

## Implementation and limitations

Requires Chrome. Selenium can manage its driver, or set CHROMEDRIVER to an installed driver path. Edit amazon_config.py to change currency, price filters, or the HTTPS base URL. Website markup and consent/captcha pages can prevent extraction; empty results are not evidence that no matching products exist. Browser certificate verification remains enabled.

## Verification

The workspace regression suite checks source/notebook validity and selected behavior with bundled or synthetic inputs. Full experiment training and historical metric reproduction are not implied. See the workspace `REFACTOR_REPORT.md` for exact test coverage and unresolved runtime requirements.
