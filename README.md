Coming soon...

* Web addres: https://atg-mission-statement.streamlit.app/



## Cloud deploy notes:

To create .yml file: conda env export > environment.yml

To create venv:
* from inside conda missionstatement run:
    * python -m venv .venv
    * .venv\Scripts\activate
    * conda deactivate (as many times as requires, since is goes back to the conda environment used just before...)

Once environment is created and packages installed: to create requirements.txt file on pure pip environment run: 
    * python -m pipreqs.pipreqs . --ignore ".venv"

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

