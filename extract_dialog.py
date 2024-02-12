#!/usr/bin/env python

from nltk import word_tokenize
from os.path import join
import logging


def read_text(text_file, encoding='UTF-8'):
    with open(text_file, 'r', encoding=encoding) as f:
        text = f.read()
    return text


def extract_dialog(text):
    """Finds dialog in the given text file, and extracts it to the target output directory, one file per character"""
    characters = {}
    narration = []
    in_quotation = False
    current_utterance = []
    current_narration = []
    speaker = None
    def ship_narration():
        nonlocal current_narration
        if current_narration:
            narration.append(' '.join(current_narration))
            current_narration = []

    def ship_quotation():
        nonlocal current_utterance
        if current_utterance:
            characters.setdefault(speaker, []).append(' '.join(current_utterance))
            current_utterance = []

    for word in word_tokenize(text):
        if word == '‘':
            in_quotation = True
            ship_narration()
            continue
        if word == '’':
            in_quotation = False
            ship_quotation()
            continue
        if in_quotation:
            current_utterance.append(word)
        else:
            current_narration.append(word)
    else:
        ship_narration()
        ship_quotation()

    return characters, narration


def save_file(target_file, sections, encoding='UTF-8'):
    with open(target_file, 'w', encoding=encoding) as f:
        word_count = 0
        for section in sections:
            f.write(section+'\n')
            word_count += len(word_tokenize(section))
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
