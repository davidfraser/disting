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

class QuotationSeparator(object):
    START = 0
    END = 1
    QUESTIONABLE_START = 2
    QUESTIONABLE_END = 3
    QUESTIONABLE_SOMETHING = 4
    QUESTIONABLE_MARKERS = {QUESTIONABLE_START, QUESTIONABLE_END, QUESTIONABLE_SOMETHING}
    QUOTATION = 5
    NARRATIVE = 6

    def __init__(self, quoting_pairs, alternative_punc=None, include_quote_marks=True):
        """Constructs a quotation separator with the given set of (start_char, end_char) quoting pairs
        If any of these can also be used as alternative punctuation chars, they should be in a alternative_punc iterable argument"""
        # doesn't yet include support for start or end markers that are more than one character
        self.quoting_pairs = quoting_pairs
        self.start_to_end = {sc: ec for sc, ec in quoting_pairs}
        self.start_chars, self.end_chars = {sc for sc, ec in quoting_pairs}, {ec for sc, ec in quoting_pairs}
        self.start_chars_re = re.compile(r"[%s]" % ''.join(sorted(set(self.start_chars))))
        self.end_chars_re = re.compile(r"[%s]" % ''.join(sorted(set(self.end_chars))))
        self.quote_chars_re = re.compile(r"[%s]" % ''.join(sorted(self.start_chars.union(self.end_chars))))
        self.alternative_punc = set() if alternative_punc is None else alternative_punc
        self.include_quote_marks = include_quote_marks
        self.in_quotation = False

    def determine_quote_marks(self, line):
        """Determines the start and end quote marks in the line
        Yields a sequence of (START|END, pos, quotechars)"""
        in_quotation = False
        for match in self.quote_chars_re.finditer(line):
            qc = match.group()
            start, end = match.span()
            potential_start = qc in self.start_chars
            potential_end = qc in self.end_chars
            could_be_alternative = qc in self.alternative_punc
            questionable = False
            if could_be_alternative:
                before = line[start-1] if start > 0 else ''
                after = line[end] if end < len(line) else ''
                if before.isalnum() and after.isalnum():
                    # this is probably a mid-word punctuation like an apostrophe
                    continue
                space_before = before.isspace() or not before
                space_after = after.isspace() or not after
                if not (space_before or space_after):
                    questionable = True
            if not questionable:
                if in_quotation is False and potential_start:
                    yield self.START, match.start(), qc
                    in_quotation = True
                    continue
                elif in_quotation is True and potential_end:
                    yield self.END, match.start(), qc
                    in_quotation = False
                    continue
            if potential_start or potential_end:
                potential_kind = (self.QUESTIONABLE_SOMETHING if potential_start and potential_end else
                                  self.QUESTIONABLE_START if potential_start else self.QUESTIONABLE_END)
                yield potential_kind, match.start(), qc

    def unquote_text(self, text, in_quotation):
        """Removes quotation marks from text and returns (start_offset, unquoted_text)"""
        if in_quotation and not self.include_quote_marks:
            for sc, ec in self.quoting_pairs:
                if text.startswith(sc) and text.endswith(ec):
                    return len(sc), text[len(sc):-len(ec)]
        return 0, text

    def split_quotes(self, line):
        """Yields a sequence of (QUOTATION|NARRATIVE, pos, subline)."""
        quote_marks = list(self.determine_quote_marks(line))
        kinds = [kind for (kind, pos, chars) in quote_marks]
        kind_counts = {kind: kinds.count(kind) for kind in set(kinds)}
        questionable = bool(self.QUESTIONABLE_MARKERS.intersection(kinds))
        if questionable:
            definite_excess = kind_counts.get(self.END, 0) - kind_counts.get(self.START, 0)
            questionable_excess = kind_counts.get(self.QUESTIONABLE_END, 0) - kind_counts.get(self.QUESTIONABLE_START, 0)

            def adjust_kind(n, new_kind):
                nonlocal definite_excess, questionable_excess
                kinds[n] = new_kind
                quote_marks[n] = (new_kind,) + quote_marks[n][1:]
                shift = {self.END: 1, self.START: -1}.get(new_kind, 0)
                definite_excess += shift
                questionable_excess -= shift

            if definite_excess < 0:
                in_quotation = False
                for n, kind in enumerate(kinds):
                    if kind == self.START:
                        in_quotation = True
                    elif in_quotation and kind == self.QUESTIONABLE_END:
                        if n+1 >= len(kinds) or kinds[n+1] != self.QUESTIONABLE_END:
                            adjust_kind(n, self.END)
                            in_quotation = False
            elif definite_excess > 0:
                in_quotation = False
                for n, kind in reversed(enumerate(kinds)):
                    if kind == self.END:
                        in_quotation = True
                    elif in_quotation and kind == self.QUESTIONABLE_START:
                        if n == 0 or kinds[n-1] != self.QUESTIONABLE_START:
                            adjust_kind(n, self.START)
                            in_quotation = False
            if definite_excess == 0:
                quote_marks = [(kind, p, c) for (kind, p, c) in quote_marks if kind not in self.QUESTIONABLE_MARKERS]
            else:
                raise ValueError(f"Unable to resolve questionable quote marks in {line}")
        last_pos, in_quotation = 0, False
        for kind, pos, chars in quote_marks + [(None, len(line), None)]:
            if in_quotation and kind == self.END:
                pos += len(chars)
            text_till_now = line[last_pos:pos]
            start_offset, unquoted_text = self.unquote_text(text_till_now, in_quotation)
            if pos > last_pos:
                yield self.QUOTATION if in_quotation else self.NARRATIVE, last_pos + start_offset, unquoted_text
            if kind == self.START:
                in_quotation = True
            elif kind == self.END:
                in_quotation = False
            elif kind is not None: # None just means the end of the text
                raise ValueError(f"Unhelpful kind {kind} at {pos} ({chars})")
            last_pos = pos

    def separate_quotations(self, text):
        """Separates the text into successive blocks, yielded as (QUOTATION|NARRATIVE, pos, subtext)
        Assumes the text has paragraphs as lines rather than line wrapping.
        Doesn't distinguish quoted foreign words etc. from quoted speech"""
        for line in text.splitlines():


            bare_line = line.strip()
            if self.in_quotation:
                # we've got another quotation starting on the following line
                starts_with_quote = self.start_chars_re.match(bare_line)
                start_positions = list(self.start_chars_re.finditer(line))
                end_positions = list(self.end_chars_re.finditer(line))

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
    parser.add_argument('-o', '--output-dir', type=str, help="Directory to output dialogue to")
    parser.add_argument('-l', '--loglevel', type=str, choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], help="Log level", default='INFO')
    args = parser.parse_args()
    logging.getLogger().setLevel(args.loglevel)
    for text_file in args.text_file:
        if not args.output_dir:
            args.output_dir = splitext(text_file)[0]
        if not exists(args.output_dir):
            os.mkdir(args.output_dir)
        text = read_text(text_file)
        characters, narration = extract_dialog(text)
        save_results(characters, narration, args.output_dir)
