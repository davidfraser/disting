Disting
=======

These are some scripts intended to help with exploration of the dialects spoken by different characters in a text.
They were developed for analysing Tolkien's works, hence the name, which is meant to emphasize
distinguishing voices of characters, as well as referencing Bilbo and later Frodo's sword Sting.

Installation
------------

Create a python virtual environment, install the requirements, and download the required source data for nltk:
```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -c "import nltk, stanza ; nltk.download('punkt') ; stanza.download('en')"
```