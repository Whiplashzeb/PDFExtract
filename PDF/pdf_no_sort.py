from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox, LTChar

import re


class PDF_No_Sort:
    def __init__(self, file_path: str):
        self.file_path = file_path

        self.abstract_flag = False
        self.main_flag = False
        self.reference_flag = False
        self.appendix_flag = False

        self.title_size = None
        self.title_font = None
        self.text_size = None
        self.text_font = None
        self.reference_size = None
        self.reference_font = None
        self.appendix_size = None
        self.appendix_font = None

        self.abstract = list()
        self.sections = dict()
        self.references = list()
        self.appendixs = dict()

        self.cur_section = None
        self.cur_subsection = None
        self.cur_append = None
        self.cur_subappend = None

        self._convert()

        self._combine()

    def _convert(self):
        first_line = False
        first_reference = False
        first_appendix = False

        try:
            for page in extract_pages(self.file_path):
                for text_box in page:
                    if isinstance(text_box, LTTextBox):
                        # print(text_box.get_text())
                        # print(text_box.bbox[0], text_box.bbox[2], page.bbox[3] - text_box.bbox[3], page.bbox[3] - text_box.bbox[1])
                        for line in text_box:
                            cur_size = None
                            cur_font = None
                            print(line.bbox[0], line.bbox[2], page.bbox[3] - line.bbox[3], page.bbox[3] - line.bbox[1])
                            line_text = line.get_text()
                            print(line_text)
                            line_text = re.sub('ﬁ', 'fi', line_text)
                            line_text = re.sub('ﬂ', 'fl', line_text)
                            line_text = re.sub('ﬀ', 'ff', line_text)
                            line_text = re.sub('ﬃ', 'ffi', line_text)

                            line_end = line_text.strip('\n').strip('.').lower()

                            if not self.abstract_flag and line_end.endswith('abstract'):
                                self.abstract_flag = True
                                continue

                            if not self.main_flag and line_end.endswith('introduction'):
                                self.main_flag = True
                                self.abstract_flag = False
                                first_line = True

                                self.cur_section = line_text.strip('\n')
                                self.cur_subsection = "start"
                                self.sections[self.cur_section] = {self.cur_subsection: list()}

                                for c in line:
                                    # 后续需要再更新
                                    if isinstance(c, LTChar):
                                        self.title_size = int(round(c.size))
                                        self.title_font = c.fontname
                                        break
                                continue

                            if self.main_flag and line_text.split(' ')[-1].split('.')[-1].lower() in {'reference\n', 'references\n'}:
                                for c in line:
                                    if isinstance(c, LTChar):
                                        cur_size = int(round(c.size))
                                        cur_font = c.fontname
                                if cur_font == self.title_font and cur_size == self.title_size and len(text_box) == 1:
                                    self.reference_flag = True
                                    self.main_flag = False
                                    first_reference = True

                                    self.cur_section = line_text.strip('\n')
                                    self.cur_subsection = "start"
                                    self.sections[self.cur_section] = {self.cur_subsection: list()}
                                    continue

                            if self.abstract_flag:
                                if len(self.abstract) != 0 and self.abstract[-1].endswith('-'):
                                    last = self.abstract.pop()
                                    line_text = last[:-1] + line_text
                                self.abstract.append(line_text.strip('\n'))

                            if self.main_flag:

                                for c in line:
                                    # 需要做的更soft
                                    if isinstance(c, LTChar):
                                        cur_size = int(round(c.size))
                                        cur_font = c.fontname
                                        if first_line:
                                            self.text_font = cur_font
                                            self.text_size = cur_size
                                            first_line = False
                                    break

                                if cur_font == self.title_font and cur_size == self.title_size and len(text_box) == 1:
                                    self.cur_section = line_text.strip('\n')
                                    self.cur_subsection = 'start'
                                    self.sections[self.cur_section] = {self.cur_subsection: list()}
                                    continue

                                if cur_font == self.title_font and cur_size == self.title_size - 1 and len(text_box) == 1:
                                    result = re.match("[\w\s\.#]+", line_text)  # 正则表达式需要更严格
                                    if result and result.span()[1] - result.span()[0] == len(line_text):
                                        self.cur_subsection = line_text.strip('\n')
                                        self.sections[self.cur_section][self.cur_subsection] = list()
                                        continue

                                if cur_size == self.text_size:  # 放松限制，目前可以有效过滤掉表格和图标中的文字
                                    cur_list = self.sections[self.cur_section][self.cur_subsection]
                                    if len(cur_list) != 0 and cur_list[-1].endswith('-'):
                                        last = cur_list.pop()
                                        line_text = last[:-1] + line_text
                                    cur_list.append(line_text.strip('\n'))

                            if self.reference_flag:
                                for c in line:
                                    # 需要做的更soft
                                    if isinstance(c, LTChar):
                                        cur_size = int(round(c.size))
                                        cur_font = c.fontname
                                        if first_reference:
                                            self.reference_font = cur_font
                                            self.reference_size = cur_size
                                            first_reference = False
                                    break

                                if cur_font == self.title_font and cur_size == self.title_size and len(text_box) == 1:
                                    self.cur_append = line_text.strip('\n')
                                    self.cur_subappend = 'start'
                                    self.appendixs[self.cur_append] = {self.cur_subappend: list()}

                                    self.appendix_flag = True
                                    self.reference_flag = False
                                    first_appendix = True
                                    continue

                                # if cur_font == self.title_font and cur_size == self.title_size - 1 and len(text_box) == 1:
                                #     result = re.match("[\w\s\.#]+", line_text)  # 正则表达式需要更严格
                                #     if result and result.span()[1] - result.span()[0] == len(line_text):
                                #         self.cur_subsection = line_text.strip('\n')
                                #         self.sections[self.cur_section][self.cur_subsection] = list()
                                #         continue

                                if cur_size == self.reference_size:
                                    if len(self.references) != 0 and self.references[-1].endswith('-'):
                                        last = self.references.pop()
                                        line_text = last[:-1] + line_text
                                    self.references.append(line_text.strip('\n'))

                            if self.appendix_flag:
                                for c in line:
                                    if isinstance(c, LTChar):
                                        cur_size = int(round(c.size))
                                        cur_font = c.fontname
                                        if cur_size == self.title_size and cur_font == self.title_font:
                                            break
                                        if first_appendix:
                                            self.appendix_size = cur_size
                                            self.appendix_font = cur_font
                                            first_appendix = False
                                        break

                                if cur_font == self.title_font and cur_size == self.title_size and len(text_box) == 1:
                                    self.cur_append = line_text.strip('\n')
                                    self.cur_subappend = 'start'
                                    self.appendixs[self.cur_append] = {self.cur_subappend: list()}
                                    continue

                                if cur_font == self.title_font and cur_size == self.title_size - 1 and len(text_box) == 1:
                                    result = re.match("[\w\s\.#]+", line_text)  # 正则表达式需要更严格
                                    if result and result.span()[1] - result.span()[0] == len(line_text):
                                        self.cur_subappend = line_text.strip('\n')
                                        self.appendixs[self.cur_append][self.cur_subappend] = list()
                                        continue

                                if cur_size == self.appendix_size:  # 放松限制，目前可以有效过滤掉表格和图标中的文字
                                    cur_list = self.appendixs[self.cur_append][self.cur_subappend]
                                    if len(cur_list) != 0 and cur_list[-1].endswith('-'):
                                        last = cur_list.pop()
                                        line_text = last[:-1] + line_text
                                    cur_list.append(line_text.strip('\n'))


                        if self.main_flag and self.cur_section and self.cur_subsection and len(self.sections[self.cur_section][self.cur_subsection]) != 0 and \
                                self.sections[self.cur_section][self.cur_subsection][-1] != "\n":
                            self.sections[self.cur_section][self.cur_subsection].append("\n")

                        if self.reference_flag and len(self.references) != 0 and self.references[-1] != "\n":
                            self.references.append("\n")

                        if self.appendix_flag and self.cur_append and self.cur_subappend and len(self.appendixs[self.cur_append][self.cur_subappend]) != 0 and \
                            self.appendixs[self.cur_append][self.cur_subappend][-1] != "\n":
                            self.appendixs[self.cur_append][self.cur_subappend].append("\n")

                if self.main_flag and self.cur_section and self.cur_subsection and len(self.sections[self.cur_section][self.cur_subsection]) != 0:
                    self.sections[self.cur_section][self.cur_subsection].pop()

                if self.reference_flag and len(self.references) != 0:
                    self.references.pop()

                if self.appendix_flag and self.cur_append and self.cur_subappend and len(self.appendixs[self.cur_append][self.cur_subappend]) != 0:
                    self.appendixs[self.cur_append][self.cur_subappend].pop()
        except Exception as e:
            print(e)

    def _combine(self):
        self.abstract = self._merge_paragraph(self.abstract)
        # print("abstract")
        # for text in self.abstract:
        #     print(text)

        for key, value in self.sections.items():
            for sub_key, sub_value in value.items():
                self.sections[key][sub_key] = self._merge_paragraph(sub_value)

        # for key, value in self.sections.items():
        #     print(key)
        #     for sub_key, sub_value in value.items():
        #         print(sub_key)
        #         for text in sub_value:
        #             print(text)

        self.references = self._merge_paragraph(self.references)
        # print("references")
        # for text in self.references:
        #     print(text)

        for key, value in self.appendixs.items():
            for sub_key, sub_value in value.items():
                self.appendixs[key][sub_key] = self._merge_paragraph(sub_value)

        # for key, value in self.appendixs.items():
        #     print(key)
        #     for sub_key, sub_value in value.items():
        #         print(sub_key)
        #         for text in sub_value:
        #             print(text)

    def _merge_paragraph(self, value):
        all_text = " ".join(value)
        text_list = all_text.split('\n')
        results = list()
        for index, text in enumerate(text_list):
            text = text.strip()
            if len(text) > 0 and text[0].isalpha() and text[0].islower() and index != 0:
                last = results.pop()
                text = last + ' ' + text
            results.append(text)

        return results

