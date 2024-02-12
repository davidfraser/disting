#!/usr/bin/env python

import nltk
import stanza
from stanza.pipeline.core import DownloadMethod
from os.path import exists, join, splitext
import os
import logging
import re


def split_at(text, marker):
    before, after = text.split(marker, 1)
    return before, marker + after

def read_text(text_file, encoding='UTF-8'):
    with open(text_file, 'r', encoding=encoding) as f:
        text = f.read()
    if ' '.join(text[:100].split()).startswith('THE LORD OF THE RINGS BY J.R.R. TOLKIEN'):
        pre_contents, contents_onwards = split_at(text, 'Contents',)
        contents, full_text = split_at(contents_onwards, 'About the Publisher')
        preface, main_text = split_at(full_text, 'THE FELLOWSHIP OF THE RING')
        main_text, indices = split_at(main_text, 'I. Poems and Songs')
        return main_text
    return text


quote_chars_re = re.compile(r"[‘’]")
resume_re = re.compile(r"[\w‘’]")

def split_quotes(sentence, in_quotation):
    last_start = 0
    for match in list(quote_chars_re.finditer(sentence)) + [None]:
        s = len(sentence) if match is None else match.start()
        is_start = sentence[s:s+1] == '‘' and (s == 0 or not sentence[s-1:s].isalnum())
        is_end = sentence[s:s+1] == '’' and not (sentence[s+1:s+2].isalnum())
        if not (is_start or is_end) and match is not None:
            # this wasn't a quote mark at all
            continue
        if is_end:
            next_resume = list(resume_re.finditer(sentence[s+1:]))
            s += (1 + next_resume[0].start()) if next_resume else (len(sentence)-s)
        section = sentence[last_start:s]
        yield section, in_quotation, is_start, is_end
        last_start = s
        if is_start:
            in_quotation = True
        if is_end:
            in_quotation = False


utter_verbs = {"say", "ask", "answer", "declare"}
indeterminate_speakers = {"they", "he", "she"}

# don't recheck each time
nlp = stanza.Pipeline('en', download_method=DownloadMethod.REUSE_RESOURCES)
# TODO: consider adding coreference, to be able to work out who 'he' is when 'he said'.

def determine_speaker(sentence):
    doc = nlp(sentence)
    for sentence in doc.sentences:
        utterance_verb = None
        utterance_mode = None
        for n, word in enumerate(sentence.words):
            if word.upos == 'VERB' and word.deprel == 'root':
                if word.lemma in utter_verbs:
                    utterance_verb, utterance_mode = word.id, 'nsubj'
                    break
                elif word.lemma == 'put':
                    # "Hello", put in so-and-so...
                    if n+1 < len(sentence.words) and sentence.words[n+1].lemma == 'in':
                        utterance_verb, utterance_mode = word.id, 'obl'
                        break
        if utterance_verb is None:
            continue
        for word in sentence.words:
            if word.head == utterance_verb and word.deprel == utterance_mode:
                speaker = word.lemma
                if not speaker in indeterminate_speakers:
                    return speaker

def extract_dialog(text, language="english"):
    """Finds dialog in the given text file, and extracts it to the target output directory, one file per character"""
    characters = {}
    narration = []
    in_quotation = False
    current_utterance = []
    current_narration = []
    speaker = None
    def ship_narration():
        nonlocal current_narration
        nonlocal speaker
        if current_narration:
            narration.append(' '.join(current_narration))
            current_narration = []

    def ship_quotation():
        nonlocal current_utterance
        if current_utterance:
            characters.setdefault(speaker, []).append(' '.join(current_utterance))
            current_utterance = []

    sentence_tokenizer = nltk.load(f"tokenizers/punkt/{language}.pickle")
    for sentence in sentence_tokenizer.tokenize(text):
        for section, in_quotation, is_start, is_end in split_quotes(sentence, in_quotation):
            if in_quotation:
                current_utterance.append(section)
            else:
                current_narration.append(section)
        if current_utterance and current_narration:
            potential_speaker = determine_speaker(sentence)
            if potential_speaker:
                speaker = potential_speaker
        ship_narration()
        ship_quotation()
    else:
        ship_narration()
        ship_quotation()

    return characters, narration


def save_file(target_file, sections, encoding='UTF-8'):
    with open(target_file, 'w', encoding=encoding) as f:
        word_count = 0
        for section in sections:
            f.write(section+'\n')
            word_count += len(nltk.word_tokenize(section))
        return (len(sections), word_count)


def save_results(characters, narration, output_dir, encoding='UTF-8'):
    for speaker, utterances in characters.items():
        speaker_file = join(output_dir, f'{speaker or "unknown"}.txt')
        section_count, word_count = save_file(speaker_file, utterances)
        logging.info("Speaker %s uttered %d utterances with %d words",
                     speaker, section_count, word_count)
    narration_file = join(output_dir, 'narration.txt')
    section_count, word_count = save_file(narration_file, narration)
    logging.info("Narrative comprised %d sections with %d words", section_count, word_count)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('text_file', nargs='+', help="File containing text")
    parser.add_argument('-o', '--output-dir', type=str, help="Directory to output dialogue to", required=True)
    parser.add_argument('-l', '--loglevel', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help="Log level", default='INFO')
    args = parser.parse_args()
    logging.getLogger().setLevel(args.loglevel)
    for text_file in args.text_file:
        text = read_text(text_file)
        characters, narration = extract_dialog(text)
        save_results(characters, narration, args.output_dir)
