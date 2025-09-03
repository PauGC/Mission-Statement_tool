Coming soon...

* Web addres: https://atg-mission-statement.streamlit.app/



Cloud deploy notes:
To create .yml file: conda env export > environment.yml
1) missionstatement (python 3.13.4):
    * initial environment created using conda and pip alternatively while writing the code in local
    * a number of fixes implemented on the fly (dirty)
    * when deploying it does not find python-docx

2) missionstatement_py311 (python 3.11.13): 
    * try package installation with conda only: I don't manage to complete the creation of the environment
        * pymupdf cannot be installed wihtout conflicting with easyocr
        * easyocr installed version by default 7.1.0, which has problems with Pillow ANTIALIAS

3) missionstatement_py313 (python 3.13.5):
    * try package installation with pip only:
        * app crashed when processing receipt images
        * processing of receipts in pdf works fine