import os
from tqdm import tqdm
import random
import json
from PDF import PDF_General
from concurrent.futures import ProcessPoolExecutor, as_completed

file_path = "../arxiv-metadata-oai-snapshot.json"
small_path = "meta_data/small_arxiv_metadata.json"

meta_dict = {}
with open(file_path, "r", encoding="utf-8") as fp:
    for line in fp.readlines():
        file_meta_data = json.loads(line)
        file_dict = dict()
        file_dict["id"] = file_meta_data["id"]
        file_dict["authors"] = file_meta_data["authors"]
        file_dict["title"] = ' '.join([x.strip() for x in file_meta_data['title'].split('\n')]).strip()
        file_dict["abstract"] = ' '.join([x.strip() for x in file_meta_data['abstract'].split('\n')]).strip()
        meta_dict[file_dict["id"]] = file_dict


def convert(file_list):
    for file_path in file_list:
        try:
            file_id = '.'.join(file_path.split('/')[-1].split('.')[:2]).split('v')[0]

            write_path = file_path.replace("pdf", "json_raw_0507", 1).replace("pdf", "json", 1)
            if os.path.exists(write_path):
                continue

            pdf_file = PDF_General(file_path)
            if pdf_file.flag:
                pdf_file.convert()
            if pdf_file.flag:
                pdf_file.combine()
            if not pdf_file.flag:
                continue
            section_content_dict = dict()

            section_content_dict["paper_type"] = pdf_file.paper_type

            for k, v in meta_dict[file_id].items():
                section_content_dict[k] = v

            section_content_dict["sections"] = pdf_file.main_text
            if len(pdf_file.references) != 0:
                section_content_dict["references"] = pdf_file.references
            if len(pdf_file.appendix) != 0:
                section_content_dict["appendix"] = pdf_file.appendix

            with open(write_path, "w") as fp:
                json_line = json.dumps(section_content_dict, ensure_ascii=False)
                fp.write(json_line)
        except Exception as e:
            if os.path.exists(write_path):
                os.remove(write_path)
            print(e)
            print(f"can't parse the file {file_path}")


if __name__ == "__main__":
    fail_list = set()
    with open("fail_files.txt") as fp:
        line = fp.readline()
        while len(line) > 0:
            line = line.strip().split('/')[-1]
            fail_list.add(line)
            line = fp.readline()

    for item in fail_list:
        print(item)
        break

    dir_list = [str(y).rjust(4, '0') for y in sorted([int(x) for x in os.listdir('../pdf')], reverse=True)]
    pdf_list = list()
    json_list = list()
    process_count = 80

    data_raw_path = "../json_raw_0507"

    if not os.path.exists(data_raw_path):
        os.mkdir(data_raw_path)

    for path_dir in dir_list:
        print(f"../pdf/{path_dir}")
        write_dir = f"../json_raw_0507/{path_dir}"
        if not os.path.exists(write_dir):
            os.mkdir(write_dir)

        pdf_list.extend(['../pdf/{}/{}'.format(path_dir, x) for x in os.listdir('../pdf/' + path_dir) if x.endswith('.pdf') and x not in fail_list])


    random.shuffle(pdf_list)
    with ProcessPoolExecutor(process_count) as executor:
        shard_size = len(pdf_list) // process_count + 1
        i = 0
        while i < len(pdf_list):
            executor.submit(convert, pdf_list[i:i + shard_size])
            i += shard_size

        # for future in as_completed(fs):
        #     result = future.result()
