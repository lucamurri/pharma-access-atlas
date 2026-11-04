# Pharma Access Atlas

How quickly, and on what terms, do new drugs reach patients in the US, Italy and Germany? A sourced
dashboard covering 30 innovative drugs approved by the FDA and the European Commission in 2019–2025.

**Live site:** https://defking1.github.io/pharma-access-atlas/

*A full README follows in the polish phase.*

## Run it locally

```bash
python3 pipeline/run_all.py --offline   # rebuild and validate the data
python3 pipeline/build_site.py          # build the site into _site/
python3 -m http.server 8000 --directory _site
```

Code: MIT licence. Data: each source's own terms, listed on the site's Methodology page.
