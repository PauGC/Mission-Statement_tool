Coming soon...

* Web addres: https://atg-mission-statement.streamlit.app/



## Streamlit cloud deployment notes:

### Working with environments
To create .yml file (from within the conda environment you want to export, of course): 
```
conda env export > environment.yml
```

To create venv:
```
python -m venv .venv
.venv\Scripts\activate
```

**NOTE:** in my case it was necessary to run it from inside conda (and in addition a specific environment, not whichever one...). This is because our F4E administrators install python through conda and there's not PYTHONPATH to a bare (pure) python installation, so one has to first use the default python path given within a conda environment. After creation and activation of venv, conda shall be fully deactivated.

Once environment is created and packages installed, to create requirements.txt file on pure pip environment run: 
```
python -m pipreqs.pipreqs . --ignore ".venv"
```

**NOTE:** ```pipreqs``` needs to be installed, but the point of exporting the requirements with ```--ignore ".venv"``` is that you just include the packages actually used in the code, not all the packages installed in your environment.

### Successful solution

In the end the best solution has been to work with venv and install all packages with pip and not use conda for anything (it does so much weird magic and ends up breaking things in non obvious ways).

Python version is 3.13. Everything works fine with that both locally and on the cloud.

The generated requirements.txt file looks like the following:

```
Babel==2.17.0
easyocr==1.7.2
numpy==2.3.2
pandas==2.3.2
Pillow==11.3.0
pycountry==24.6.1
pymupdf==1.26.4
python_docx==1.2.0
streamlit==1.49.1
```

Additionally, a reduction of the receipt images to a size of roughly 200 kB before being processed with easyocr was necessary to avoid easyocr.Reader.readtext to crash when recognizing text from the images.

### Environments tests

1) missionstatement (python 3.13.4):
    * mixed conda and pip package installation 
    * initial environment created while writing the code locally
        * locally: works fine after a number of fixes implemented while writing the code
            - in app.py, utils\utils.py: os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
            - in utils\utils.py: torch.classes.__path__ = []
        * cloud:
            - environment.yml: when deploying it does not find python-docx
            - requirements.txt: 
                - when placing python-docx first, no problems with python-docx
                - app crashes when loading easyocr model (easyocr.Reader)

2) missionstatement_py311 (python 3.11.13): 
    * pure conda installation: I don't manage to complete the creation of the environment
        * pymupdf cannot be installed wihtout conflicting with easyocr
        * easyocr installed version by default 7.1.0, which has problems with Pillow ANTIALIAS

3) missionstatement_py312 (python 3.12.11):
    * conda env with only pip installation:
        * locally:
            - app crashes when processing receipt images (easyocr, Pillow?!?!?!)
            - processing of receipts in pdf works fine
        * cloud:
            - does not find python-docx...

4) missionstatement_py313 (python 3.13.5):
    * conda env with only pip installation:
        * locally:
            - app crashes when processing receipt images (easyocr, Pillow?!?!?!)
            - processing of receipts in pdf works fine
        * cloud:
            - does not find python-docx...

