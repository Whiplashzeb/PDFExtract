from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextBox, LTChar

import re
import nltk
from collections import Counter


class PDF_ACL(object):
    def __init__(self, input_file_path: str):
        self.input_file_path = input_file_path
        self.flag = True
        self.file_id = input_file_path.split('/')[-1].split('.')[0]

        try:
            self.pages = extract_pages(input_file_path)
        except Exception as e:
            self.flag = False
            print("pdf_miner can't parse the file", self.input_file_path)

        self.tokenizer = nltk.data.load("tokenizers/punkt/english.pickle")
        self.paper_type = None

        self.height = None
        self.width = None

        self.abstract_flag = False
        self.main_flag = False
        self.reference_flag = False
        self.appendix_flag = False

        self.abstract_font = None
        self.abstract_size = None
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
        self.main_text = list()
        self.references = list()
        self.appendix = dict()
        self.append_text = list()

        self.cur_section = None
        self.cur_subsection = None
        self.cur_append = None
        self.cur_subappend = None



    def _get_size_and_font(self, line):
        font = Counter()
        size = Counter()
        for c in line:
            if isinstance(c, LTChar):
                font[c.fontname] += 1
                size[c.size] += 1

        font = font.most_common(1)[0][0]
        size = size.most_common(1)[0][0]

        return font, size

    def _clean_text_line(self, line):
        line_text = line.get_text()

        line_text = re.sub("ﬁ", "fi", line_text)
        line_text = re.sub("ﬂ", "fl", line_text)
        line_text = re.sub("ﬀ", "ff", line_text)
        line_text = re.sub("ﬃ", "ffi", line_text)
        line_text = re.sub("\r", "c", line_text)
        line_text = re.sub("℄", "]", line_text)

        return line_text

    def _extract_information_from_first_page(self, page):
        """
        通过第一页文本判断论文类型
        -1: 论文中无法解析出text_box
        0：只能获取到正文的size和font
        1：可以获取到introduction，但是size和font与正文相同
        2：可以获取到introduction， size和font都与正文不同
        3：可以获取到introduction，size不同，font相同
        4：可以获取到introduction， size相同，font不同
        :param page:
        :return:
        """
        title_flag = False
        most_size = Counter()
        most_font = Counter()

        for text_box in page:
            if isinstance(text_box, LTTextBox):
                line = list(text_box)[0]
                for c in line:
                    if isinstance(c, LTChar):
                        most_size[c.size] += 1
                        most_font[c.fontname] += 1

                if not title_flag and len(text_box) == 1:
                    line_text = self._clean_text_line(text_box)
                    line_text = line_text.strip().strip('.').lower()
                    result = re.match("[\d \.I]*introduction.*", line_text)
                    if (result or line_text.endswith("introduction")) and len(line_text) <= 50:
                        title_flag = True
                        line = list(text_box)[0]
                        font, size = self._get_size_and_font(line)

                        self.title_font = font
                        self.title_size = size
                        continue

        if len(most_size) == 0:
            return -1

        self.text_size = most_size.most_common(1)[0][0]
        self.text_font = most_font.most_common(1)[0][0]

        if self.title_size is None:
            return 0
        if self.text_font == self.title_font and self.text_size == self.title_size:
            return 1
        if self.text_size != self.title_size and self.text_font != self.title_font:
            return 2
        if self.text_size != self.title_size and self.text_font == self.title_font:
            return 3
        if self.text_size == self.title_size and self.text_font != self.title_font:
            return 4

    def convert(self):
        if not self.flag:
            return
        try:
            first_page = None
            for page in extract_pages(self.input_file_path):
                first_page = page
                break

            if first_page is None:
                return

            self.height = first_page.bbox[3]
            self.width = first_page.bbox[2]
            paper_type = self._extract_information_from_first_page(first_page)
            self.paper_type = paper_type

            if self.paper_type == -1:
                self.flag = False
                print("can't get text_box in file", self.input_file_path)

            if self.paper_type == 0 or self.paper_type == 1:
                self._convert_type_0()
            elif self.paper_type == 2 or self.paper_type == 3 or self.paper_type == 4:
                self._convert_type_1()

        except Exception as e:
            print(e)
            self.flag = False
            print("can't convert the file ", self.input_file_path)

    def _convert_type_0(self):
        cur_boxes = list()
        first_abstract = True
        first_reference = True
        first_appendix = True

        for page in self.pages:
            cur_boxes.append(list())
            for text_box in page:
                # print(text_box)
                if isinstance(text_box, LTTextBox):
                    line = list(text_box)[0]
                    line_text = self._clean_text_line(line)
                    line_text = line_text.strip().strip('.').lower()

                    if not self.abstract_flag and len(text_box) == 1 and line_text.endswith("abstract"):
                        self.abstract_flag = True
                        cur_boxes = [[]]
                        continue

                    if not self.reference_flag and len(text_box) == 1 and line_text in {"reference", "references"}:
                        self.reference_flag = True
                        self.main_flag = False

                        if self.main_flag:
                            if self.cur_section and self.cur_subsection:
                                self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)
                        else:
                            self.abstract = self._sort_boxes(cur_boxes)

                        cur_boxes = [[]]
                        continue

                    if not self.appendix_flag and len(text_box) == 1 and line_text.find("appendix") != -1 and len(line_text) < 100:
                        cur_font, cur_size = self._get_size_and_font(line)
                        if cur_font == self.title_font and cur_size == self.title_size:
                            self.appendix_flag = True

                            if self.reference_flag:
                                self.references = self._sort_boxes(cur_boxes)
                            elif self.main_flag:
                                if self.cur_section and self.cur_subsection:
                                    self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)
                            else:
                                self.abstract = self._sort_boxes(cur_boxes)

                            cur_boxes = [[]]
                            continue

                    if self.abstract_flag:
                        cur_font, cur_size = self._get_size_and_font(line)
                        if first_abstract:
                            self.abstract_font, self.abstract_size = cur_font, cur_size
                            first_abstract = False

                        if cur_size > self.abstract_size and len(text_box) == 1:
                            self.main_flag = True
                            self.abstract_flag = False

                            self.cur_section = line_text.strip('\n')
                            self.cur_subsection = "start"
                            self.sections[self.cur_section] = {self.cur_subsection: list()}

                            self.title_font = cur_font
                            self.title_size = cur_size

                            self.abstract = self._sort_boxes(cur_boxes)
                            cur_boxes = [[]]
                            continue

                        if cur_size == self.abstract_size and cur_font == self.abstract_font:
                            cur_boxes[-1].append((text_box, (int(text_box.bbox[0]), int(text_box.bbox[2]), int(self.height - text_box.bbox[3]), int(self.height - text_box.bbox[1]))))

                    if self.main_flag:
                        cur_font, cur_size = self._get_size_and_font(line)

                        if len(text_box) == 1 and cur_font == self.title_font and cur_size == self.title_size:
                            if self.cur_section and self.cur_subsection:
                                self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)

                                self.cur_section = line_text.strip('\n')
                                self.cur_subsection = "Start"
                                self.sections[self.cur_section] = {self.cur_subsection: list()}
                                cur_boxes = [[]]
                                continue

                        if len(text_box) == 1 and cur_font == self.title_font and cur_size == self.title_size - 1:
                            result = re.match("[\w\s\.#]+", line_text)  # 正则表达式需要更严格
                            if result and result.span()[1] - result.span()[0] == len(line_text):
                                if self.cur_section and self.cur_subsection:
                                    self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)

                                    self.cur_subsection = line_text.strip('\n')
                                    self.sections[self.cur_section][self.cur_subsection] = list()
                                    cur_boxes = [[]]

                                continue

                        if cur_size == self.text_size and cur_font == self.text_font:
                            cur_boxes[-1].append((text_box, (int(text_box.bbox[0]), int(text_box.bbox[2]), int(self.height - text_box.bbox[3]), int(self.height - text_box.bbox[1]))))

                    if self.reference_flag:
                        cur_font, cur_size = self._get_size_and_font(line)
                        if first_reference:
                            self.reference_font = cur_font
                            self.reference_size = cur_size
                            first_reference = False

                        if cur_font == self.title_font and cur_size == self.title_size and len(text_box) == 1:
                            self.appendix_flag = True
                            self.reference_flag = False

                            self.cur_append = line_text.strip('\n')
                            self.cur_subappend = 'Start'
                            self.appendix[self.cur_append] = {self.cur_subappend: list()}

                            self.references = self._sort_boxes(cur_boxes)

                        if cur_size == self.reference_size and cur_font == self.reference_font:
                            cur_boxes[-1].append((text_box, (int(text_box.bbox[0]), int(text_box.bbox[2]), int(self.height - text_box.bbox[3]), int(self.height - text_box.bbox[1]))))

                    if self.appendix_flag:
                        cur_font, cur_size = self._get_size_and_font(line)
                        if first_appendix:
                            self.appendix_font = cur_font
                            self.appendix_size = cur_size
                            first_appendix = False

                        if cur_font == self.title_font and cur_size == self.title_size and len(text_box) == 1:
                            if self.cur_append and self.cur_subappend:
                                self.appendix[self.cur_append][self.cur_subappend] = self._sort_boxes(cur_boxes)

                            self.cur_append = line_text.strip('\n')
                            self.cur_subappend = 'Start'
                            self.appendix[self.cur_append] = {self.cur_subappend: list()}

                            cur_boxes = [[]]
                            continue

                        if cur_font == self.title_font and cur_size == self.title_size - 1 and len(text_box) == 1:
                            result = re.match("[\w\s\.#]+", line_text)  # 正则表达式需要更严格
                            if result and result.span()[1] - result.span()[0] == len(line_text):
                                if self.cur_append and self.cur_subappend:
                                    self.appendix[self.cur_append][self.cur_subappend] = self._sort_boxes(cur_boxes)
                                    self.cur_subappend = line_text.strip('\n')
                                    self.sections[self.cur_append][self.cur_subappend] = list()
                                    cur_boxes = [[]]
                                continue

                        if cur_size == self.appendix_size and cur_font == self.appendix_font:
                            cur_boxes[-1].append((text_box, (int(text_box.bbox[0]), int(text_box.bbox[2]), int(self.height - text_box.bbox[3]), int(self.height - text_box.bbox[1]))))

        if self.cur_append and self.cur_subappend:
            self.appendix[self.cur_append][self.cur_subappend] = self._sort_boxes(cur_boxes)
        elif self.reference_flag:
            self.references = self._sort_boxes(cur_boxes)
        elif self.main_flag:
            if self.cur_section and self.cur_subsection:
                self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)
        else:
            self.abstract = self._sort_boxes(cur_boxes)

    def _convert_type_1(self):
        cur_boxes = list()
        first_abstract = True
        first_reference = True
        first_appendix = True

        for page in self.pages:
            cur_boxes.append(list())
            for text_box in page:
                # print(text_box)
                if isinstance(text_box, LTTextBox):
                    line = list(text_box)[0]
                    line_text = self._clean_text_line(line)
                    line_text = line_text.strip().strip('.').lower()

                    if not self.abstract_flag and len(text_box) == 1 and line_text.endswith("abstract"):
                        self.abstract_flag = True
                        cur_boxes = [[]]
                        continue

                    if not self.main_flag:
                        result = re.match("[\d \.I]*introduction.*", line_text)
                        if (result or line_text.endswith("introduction")) and len(line_text) <= 50:
                            self.main_flag = True
                            self.abstract_flag = False

                            self.cur_section = line_text.strip('\n')
                            self.cur_subsection = "start"
                            self.sections[self.cur_section] = {self.cur_subsection: list()}

                            self.abstract = self._sort_boxes(cur_boxes)
                            cur_boxes = [[]]
                            continue

                    if not self.reference_flag and len(text_box) == 1 and line_text in {"reference", "references"}:
                        self.reference_flag = True
                        self.main_flag = False

                        if self.cur_section and self.cur_subsection:
                            self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)

                        cur_boxes = [[]]
                        continue

                    if not self.appendix_flag and len(text_box) == 1 and line_text.find("appendix") != -1 and len(line_text) < 100:
                        cur_font, cur_size = self._get_size_and_font(line)
                        if cur_font == self.title_font and cur_size == self.title_size:
                            self.appendix_flag = True

                            if self.reference_flag:
                                self.references = self._sort_boxes(cur_boxes)
                            else:
                                if self.cur_section and self.cur_subsection:
                                    self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)

                            cur_boxes = [[]]
                            continue

                    if self.abstract_flag:
                        cur_font, cur_size = self._get_size_and_font(line)
                        if first_abstract:
                            self.abstract_font, self.abstract_size = cur_font, cur_size
                            first_abstract = False

                        if cur_size == self.abstract_size and cur_font == self.abstract_font:
                            cur_boxes[-1].append((text_box, (int(text_box.bbox[0]), int(text_box.bbox[2]), int(self.height - text_box.bbox[3]), int(self.height - text_box.bbox[1]))))

                    if self.main_flag:
                        cur_font, cur_size = self._get_size_and_font(line)

                        if len(text_box) == 1 and cur_font == self.title_font and cur_size == self.title_size:
                            if self.cur_section and self.cur_subsection:
                                self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)

                                self.cur_section = line_text.strip('\n')
                                self.cur_subsection = "Start"
                                self.sections[self.cur_section] = {self.cur_subsection: list()}
                                cur_boxes = [[]]
                                continue

                        if len(text_box) == 1 and cur_font == self.title_font and cur_size == self.title_size - 1:
                            result = re.match("[\w\s\.#]+", line_text)  # 正则表达式需要更严格
                            if result and result.span()[1] - result.span()[0] == len(line_text):
                                if self.cur_section and self.cur_subsection:
                                    self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)

                                    self.cur_subsection = line_text.strip('\n')
                                    self.sections[self.cur_section][self.cur_subsection] = list()
                                    cur_boxes = [[]]

                                continue

                        if cur_size == self.text_size and cur_font == self.text_font:
                            cur_boxes[-1].append((text_box, (int(text_box.bbox[0]), int(text_box.bbox[2]), int(self.height - text_box.bbox[3]), int(self.height - text_box.bbox[1]))))

                    if self.reference_flag:
                        cur_font, cur_size = self._get_size_and_font(line)
                        if first_reference:
                            self.reference_font = cur_font
                            self.reference_size = cur_size
                            first_reference = False

                        if cur_font == self.title_font and cur_size == self.title_size and len(text_box) == 1:
                            self.appendix_flag = True
                            self.reference_flag = False

                            self.cur_append = line_text.strip('\n')
                            self.cur_subappend = 'Start'
                            self.appendix[self.cur_append] = {self.cur_subappend: list()}

                            self.references = self._sort_boxes(cur_boxes)

                        if cur_size == self.reference_size and cur_font == self.reference_font:
                            cur_boxes[-1].append((text_box, (int(text_box.bbox[0]), int(text_box.bbox[2]), int(self.height - text_box.bbox[3]), int(self.height - text_box.bbox[1]))))

                    if self.appendix_flag:
                        cur_font, cur_size = self._get_size_and_font(line)
                        if first_appendix:
                            self.appendix_font = cur_font
                            self.appendix_size = cur_size
                            first_appendix = False

                        if cur_font == self.title_font and cur_size == self.title_size and len(text_box) == 1:
                            if self.cur_append and self.cur_subappend:
                                self.appendix[self.cur_append][self.cur_subappend] = self._sort_boxes(cur_boxes)

                            self.cur_append = line_text.strip('\n')
                            self.cur_subappend = 'Start'
                            self.appendix[self.cur_append] = {self.cur_subappend: list()}

                            cur_boxes = [[]]
                            continue

                        if cur_font == self.title_font and cur_size == self.title_size - 1 and len(text_box) == 1:
                            result = re.match("[\w\s\.#]+", line_text)  # 正则表达式需要更严格
                            if result and result.span()[1] - result.span()[0] == len(line_text):
                                if self.cur_append and self.cur_subappend:
                                    self.appendix[self.cur_append][self.cur_subappend] = self._sort_boxes(cur_boxes)
                                    self.cur_subappend = line_text.strip('\n')
                                    self.sections[self.cur_append][self.cur_subappend] = list()
                                    cur_boxes = [[]]
                                continue

                        if cur_size == self.appendix_size and cur_font == self.appendix_font:
                            cur_boxes[-1].append((text_box, (int(text_box.bbox[0]), int(text_box.bbox[2]), int(self.height - text_box.bbox[3]), int(self.height - text_box.bbox[1]))))

        if self.cur_append and self.cur_subappend:
            self.appendix[self.cur_append][self.cur_subappend] = self._sort_boxes(cur_boxes)
        elif self.reference_flag:
            self.references = self._sort_boxes(cur_boxes)
        else:
            if self.cur_section and self.cur_subsection:
                self.sections[self.cur_section][self.cur_subsection] = self._sort_boxes(cur_boxes)

    def _detect_cover(self, box_1, box_2, i, j):
        """
        检测两个text_box是否需要合并
        1： 2在1内
        2： 1在2内
        3： 在同一行中，1在前
        4： 在同一行中，1在后
        5： 有交叉（只有相邻的块判断交叉）
        0：无上述情况
        :param box_1:
        :param box_2:
        :param i:
        :param j:
        :return:
        """
        box_1_pos = box_1[1]
        box_2_pos = box_2[1]
        if box_1_pos[0] <= box_2_pos[0] and box_1_pos[1] >= box_2_pos[1] and box_1_pos[2] <= box_2_pos[2] and box_1_pos[3] >= box_2_pos[3]:
            return 1
        if box_2_pos[0] <= box_1_pos[0] and box_2_pos[1] >= box_1_pos[1] and box_2_pos[2] <= box_1_pos[2] and box_2_pos[3] >= box_1_pos[3]:
            return 2
        if box_1_pos[2] == box_2_pos[2] and box_1_pos[3] == box_2_pos[3] and box_1_pos[0] < box_2_pos[0]:
            return 3
        if box_1_pos[2] == box_2_pos[2] and box_1_pos[3] == box_2_pos[3] and box_2_pos[0] < box_1_pos[0]:
            return 4
        minx = max(box_1_pos[0], box_2_pos[0])
        miny = max(box_1_pos[2], box_2_pos[2])

        maxx = min(box_1_pos[1], box_2_pos[1])
        maxy = min(box_1_pos[3], box_2_pos[3])
        if not (minx >= maxx or miny >= maxy) and j - i == 1:
            return 5
        return 0

    def _merge_cover_line(self, cur_line):
        line_text = ""
        cur_line = sorted(cur_line, key=lambda a: a[1][0])
        for i in cur_line:
            text = self._clean_text_line(i[0])
            line_text += text.strip()
            line_text += ' '
        return line_text.strip()

    def _merge_cover_blocks(self, key, value, cur_page):
        block = list()

        text_line_list = list()
        for line in cur_page[key][0]:
            text_line_list.append((line, (int(round(line.bbox[0])), int(round(line.bbox[2])), int(round(self.height - line.bbox[3])), int(round(self.height - line.bbox[1])))))

        if value is not None:
            for index in value:
                for line in cur_page[index][0]:
                    text_line_list.append(
                        (line, (int(round(line.bbox[0])), int(round(line.bbox[2])), int(round(self.height - line.bbox[3])), int(round(self.height - line.bbox[1])))))

            text_line_list = sorted(text_line_list, key=lambda a: a[1][2])

        cur_y1, cur_y2 = None, None
        cur_line = list()
        for line in text_line_list:
            if len(cur_line) == 0:
                cur_line.append(line)
                cur_y1, cur_y2 = line[1][2], line[1][3]
                continue

            if cur_y1 != line[1][2] and cur_y2 != line[1][3]:
                line_text = self._merge_cover_line(cur_line)
                # if len(cur_line) > 1:
                #     line_text = self._merge_cover_line(cur_line)
                # else:
                #     line_text = self._clean_text_line(cur_line[0][0])
                if len(block) != 0 and block[-1].endswith('-'):
                    last = block.pop()
                    line_text = last[:-1] + line_text
                block.append(line_text.strip('\n'))
                cur_line = [line]
                cur_y1, cur_y2 = line[1][2], line[1][3]
            else:
                cur_line.append(line)

        if len(cur_line) > 1:
            line_text = self._merge_cover_line(cur_line)
        else:
            line_text = self._clean_text_line(cur_line[0][0])
        if len(block) != 0 and block[-1].endswith('-'):
            last = block.pop()
            line_text = last[:-1] + line_text
        block.append(line_text.strip('\n'))
        return block

    def _sort_page(self, cur_page):
        block = list()

        merge = dict()
        interactive = list()

        index_list = [i for i in range(len(cur_page))]

        for i in range(len(cur_page) - 1):
            for j in range(i + 1, len(cur_page)):
                cover = self._detect_cover(cur_page[i], cur_page[j], i, j)
                if cover == 2:
                    if i in index_list:
                        index_list.remove(i)
                    if j in merge.keys():
                        merge[j].append(i)
                    else:
                        merge[j] = [i]
                if cover == 1:
                    if j in index_list:
                        index_list.remove(j)
                    if i in merge.keys():
                        merge[i].append(j)
                    else:
                        merge[i] = [j]
                if cover == 5 or cover == 4 or cover == 3:
                    interactive.append((i, j))

        for i, j in interactive:
            flag = True
            if i in merge.keys():
                merge[i].append(j)
                if j in index_list:
                    index_list.remove(j)
                flag = False
                continue
            if j in merge.keys():
                merge[j].append(i)
                if i in index_list:
                    index_list.remove(i)
                flag = False
                continue
            for k, v in merge.items():
                if i in v and j not in v:
                    merge[k].append(j)
                    if j in index_list:
                        index_list.remove(j)
                    flag = False
                    break
                if j in v and i not in v:
                    merge[k].append(i)
                    if i in index_list:
                        index_list.remove(i)
                    flag = False
                    break

            if flag:
                merge[i] = [j]
                if j in index_list:
                    index_list.remove(j)

        for i in index_list:
            if i in merge.keys():
                cover = self._merge_cover_blocks(key=i, value=merge[i], cur_page=cur_page)
            else:
                cover = self._merge_cover_blocks(key=i, value=None, cur_page=cur_page)
            if len(block) > 0 and block[-1].endswith('-') and len(cover) != 0:
                last = block.pop()
                cover[0] = last[:-1] + cover[0]
            block.extend(cover)

            if len(block) != 0 and block[-1] != '\n':
                block.append('\n')

        return block

    def _sort_boxes(self, cur_boxes):
        results = list()
        for cur_page in cur_boxes:
            block = self._sort_page(cur_page)
            if len(block) > 0:
                block.pop()
                if len(results) != 0 and results[-1].endswith('-') and len(block) != 0:
                    last = results.pop()
                    block[0] = last[:-1] + block[0]
                results.extend(block)

        return results

    def _too_many_other_char(self, line):
        cnt = 0
        for digit in line.lower():
            if digit in set([chr(ord('a') + i) for i in range(26)] + ['%', '.']):
                cnt += 1
        if cnt / len(line) <= 0.5:
            return True
        return False

    def _get_start_pos(self, line):
        for idx, c in enumerate(line):
            if c.lower() in set([chr(ord('a') + i) for i in range(26)]) or c == "[" or c in set([chr(ord('0') + i) for i in range(10)]):
                return idx
        return -1

    def _clean_text(self, line):
        result = ""
        sentences = self.tokenizer.tokenize(line)
        # print(sentences)
        for sentence in sentences:
            if len(sentence) < 8 or "cid" in sentence:
                # print("filter:", sentence)
                continue
            start_legal = re.match("[A-Za-z0-9\[]", sentence[0])
            end_legal = re.match("[?.!\];\"~,:]", sentence[-1])
            if not start_legal or not end_legal:
                # print("filter:", sentence)
                continue
            if self._too_many_other_char(sentence):
                # print("filter:", sentence)
                continue
            sentence = sentence[self._get_start_pos(sentence):]
            result += sentence + " "

        return result

    def _merge_paragraph(self, value):
        result = list()

        all_text = ' '.join(value)
        text_list = all_text.split('\n')

        for index, text in enumerate(text_list):
            text = text.strip()
            if len(text) > 0 and text[0].isalpha() and text[0].islower() and index != 0:
                last = result.pop()
                if len(last) != 0 and last[-1] == "-":
                    text = last[:-1] + text
                else:
                    text = last + ' ' + text
            result.append(text)

        clean_result = list()
        for text in result:
            if len(text) < 22:
                continue
            clean_text = self._clean_text(text)
            if len(clean_text) > 0:
                clean_result.append(clean_text)
        return "\n".join(clean_result)

    def _merge_references(self, value):
        result = list()

        all_text = ' '.join(value)
        text_list = all_text.split('\n')
        for index, text in enumerate(text_list):
            text = text.strip()
            if len(text) > 0 and text[0].isalpha() and text[0].islower() and index != 0:
                last = result.pop()
                if len(last) != 0 and last[-1] == "-":
                    text = last[:-1] + text
                else:
                    text = last + '\n' + text
            result.append(text)

        return "\n".join(result)

    def combine(self):
        if self.abstract_flag:
            self.abstract = self._merge_paragraph(self.abstract)
        for key, value in self.sections.items():
            print(key, value)
            section = dict()
            section["key"] = key
            section["section"] = list()
            for sub_key, sub_value in value.items():
                sub_section = dict()
                sub_section["sub_key"] = sub_key
                sub_section["text"] = self._merge_paragraph(sub_value)
            self.main_text.append(section)
        self.references = self._merge_references(self.references)
        if self.appendix_flag:
            for key, value in self.appendix.items():
                section = dict()
                section["key"] = key
                section["section"] = list()
                for sub_key, sub_value in value.items():
                    sub_section = dict()
                    sub_section["sub_key"] = sub_key
                    sub_section["text"] = self._merge_paragraph(sub_value)
                self.append_text.append(section)
