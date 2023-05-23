import re
import os
import git
import shutil
import urllib.request
import json
import uuid
from pathlib import Path


src_dir = 'lkmpg'
temp_tex = src_dir + '/temp.tex'
trg_dir = '.'
temp_md = trg_dir + '/temp.md'

current_chapter = 0
current_section = 0


base_url = "https://wikidocs.net/"
chapters = [
    ("0", "Title", "196791"),
    ("1", "Introduction", "196792"),
    ("2", "Headers", "196793"),
    ("3", "Examples", "196794"),
    ("4", "Hello World", "196795"),
    ("5", "Preliminaries", "196796"),
    ("6", "Character Device drivers", "196797"),
    ("7", "The /proc File System", "196798"),
    ("8", "sysfs: Interacting with your module", "196799"),
    ("9", "Talking To Device Files", "196800"),
    ("10", "System Calls", "196801"),
    ("11", "Blocking Processes and threads", "196803"),
    ("12", "Avoiding Collisions and Deadlocks", "196804"),
    ("13", "Replacing Print Macros", "196805"),
    ("14", "Scheduling Tasks", "196806"),
    ("15", "Interrupt Handlers", "196807"),
    ("16", "Crypto", "196808"),
    ("17", "Virtual Input Device Driver", "196809"),
    ("18", "Standardizing the interfaces: The Device Model", "196810"),
    ("19", "Optimizations", "196811"),
    ("20", "Common Pitfalls", "196812"),
    ("21", "Where To Go From Here?", "196813"),
]


def pull_en():
    repo = git.Repo(src_dir)
    origin = repo.remotes.origin
    origin.pull()


def include_external_code(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
    return content


def include_samplec(content):
    matches = re.finditer(r'\\samplec\{(.+?)\}', content)
    for match in matches:
        code_file_path = match.group(1)
        code_content = include_external_code(src_dir + '/' + code_file_path)
        content = content.replace(match.group(0), f'\\begin{{verbatim}}\n{code_content}\n\\end{{verbatim}}')
    return content


def replace_code(content):
    content = re.sub(r'\\begin\{code\}', r'\\begin{verbatim}', content)
    content = re.sub(r'\\end\{code\}', r'\\end{verbatim}', content)
    return content


def replace_codebash(content):
    content = re.sub(r'\\begin\{codebash\}', r'\\begin{verbatim}', content)
    content = re.sub(r'\\end\{codebash\}', r'\\end{verbatim}', content)
    return content


def convert_verbatim_to_temp_tex(content):
    verbatim_pattern = r'\\(?:cpp)?\|(.+?)\|'
    matches = re.finditer(verbatim_pattern, content)
    for match in matches:
        original_text = match.group(0)
        code_text = match.group(1)
        replacement = f'\\texttt{{{code_text}}}'
        content = content.replace(original_text, replacement)
    return content


def replace_image_references(tex_content):
    image_counter = 1
    img_pattern = r'Figure~\\ref{img:(.+?)}'
    matches = re.finditer(img_pattern, tex_content)

    for match in matches:
        img_id = match.group(1)
        original_text = match.group(0)

        # Replace the image reference
        replacement = f"Figure {image_counter}"
        tex_content = tex_content.replace(original_text, replacement)

        image_counter += 1

    return tex_content


def replace_figures_with_captions(tex_content):
    image_counter = 1
    figure_pattern = r'\\begin{figure}.*?\\caption{(.*?)}.*?\\end{figure}'
    matches = re.finditer(figure_pattern, tex_content, flags=re.DOTALL)

    for match in matches:
        original_text = match.group(0)
        caption_text = match.group(1)

        # Replace the figure with the caption text and image placeholder
        replacement = f"<!-- image {image_counter} -->\n\nFigure {image_counter}: {caption_text}"
        tex_content = tex_content.replace(original_text, replacement, 1)

        image_counter += 1

    return tex_content


def add_section_numbers(content):
    global current_chapter
    global current_section
    
    chapter_pattern = r'\n# (.+)(\{#.+?\})*'  # some chapter has no ref
    section_pattern = r'\s## (.+?)\s*\{#(.+?)\}'

    matches = list(re.finditer(chapter_pattern, content)) + list(re.finditer(section_pattern, content))
    matches.sort(key=lambda match: match.start())

    for match in matches:
        if match.re.pattern == chapter_pattern:
            current_chapter += 1
            current_section = 0
            section_title = match.group(1)
            replacement = f'{current_chapter}. {section_title}'
        else:
            current_section += 1
            section_title = match.group(1)
            label = match.group(2)
            replacement = f'{current_chapter}.{current_section}. {section_title}'

        content = content.replace(match.group(1), replacement)

    return content


ref_dic = {}


def populate_ref_dic(content):
    chapter_pattern = r'# (\d+?)\. (.+?)\s*\{#(.+?)\}'
    section_pattern = r'## (\d+?\.\d+?)\. (.+?)\s*\{#(.+?)\}'
    standalone_label_pattern = r'.*\[\\\[(.+?)\\\]\]\{#(.+?) label="(.+?)"\}.*'

    page_map = get_page_map()
    current_section = 0
    
    for line in content.split('\n'):
        chapter_match = re.match(chapter_pattern, line)
        if chapter_match:
            current_section = chapter_match.group(1)
            ref_dic[chapter_match.group(3)] = current_section
        
        section_match = re.match(section_pattern, line)
        if section_match:
            current_section = section_match.group(1)
            ref_dic[section_match.group(3)] = current_section
        
        standalone_label_match = re.match(standalone_label_pattern, line)
        if standalone_label_match:
            ref_dic[standalone_label_match.group(3)] = current_section
            


def convert_section_references(content):
    chapter_pattern = r'\s# (.+?)\s*\{#(.+?)\}'
    section_pattern = r'\s## (.+?)\s*\{#(.+?)\}'

    chapter_matches = list(re.finditer(chapter_pattern, content))
    section_matches = list(re.finditer(section_pattern, content))

    # Remove chapter labels
    for match in chapter_matches:
        chapter_title = match.group(1)
        label = match.group(2)
        replacement = f'\n# {chapter_title}'
        content = content.replace(match.group(0), replacement)

    # Add anchor tags for sections
    for match in section_matches:
        section_title = match.group(1)
        label = match.group(2)
        replacement = f'\n<a name="{label}"></a>\n\n## {section_title}'
        content = content.replace(match.group(0), replacement)

    return content


def convert_reference_labels(md_content):
    ref_pattern = r'\[\\\[(.+?)\\\]\]{#(.+?) label="(.+?)"}'
    matches = re.finditer(ref_pattern, md_content)

    for match in matches:
        original_text = match.group(0)
        sec_name = match.group(1)
        label_name = match.group(3)
        replacement = f'<a name="{label_name}"></a>'
        md_content = md_content.replace(original_text, replacement)

    return md_content


def get_page_map():
    page_map = {}
    for number, name, page_id in chapters:
        page_map[str(number)] = page_id
    return page_map


def convert_refs(content):
    ref_pattern = r'\[(.+?)\]\(#(.+?)\)\{reference-type="ref" reference="(.+?)"\}'
    matches = re.finditer(ref_pattern, content)
    for match in matches:
        chapter_number = match.group(1).split('.')[0]
        anchor = match.group(2)
        label = match.group(3)
        page_map = get_page_map()
        page_id = page_map.get(chapter_number)
        if '.' in match.group(1):
            replacement = f'[{match.group(1)}]({base_url}{page_id}#{anchor})'
        elif re.match('\d+', match.group(1)):
            replacement = f'[{match.group(1)}]({base_url}{page_id})'
        else:
            section_number = ref_dic[match.group(3)]
            page_id = page_map.get(section_number.split('.')[0])
            replacement = f'[{section_number}]({base_url}{page_id}#{anchor})'
        content = content.replace(match.group(0), replacement)
    return content


def convert_urls(content):
    url_pattern = r'\[\]\((https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/(.+?))\)'
    matches = re.finditer(url_pattern, content)
    for match in matches:
        full_url = match.group(1)
        file_name = match.group(2)
        replacement = f'[{file_name}]({full_url})'
        content = content.replace(match.group(0), replacement)
    return content


def convert_verbatim_and_commands(content):
    # First convert \|(.+?)\| to `(.+?)`
    verbatim_pattern = r'\\\|(.+?)\\\|'
    matches = re.finditer(verbatim_pattern, content)
    for match in matches:
        original_text = match.group(0)
        code_text = match.group(1)
        replacement = f"`{code_text}`"
        content = content.replace(original_text, replacement)
        
    content = content.replace("`cp /boot/config-'uname -r' .config`", r"`` cp /boot/config-`uname -r` .config ``")
    content = content.replace("`linux-'uname -r'`", r"`` linux-`uname -r` ``")

    return content


def remove_flushleft_md(content):
    content = content.replace('\n::: flushleft', '')
    content = content.replace('\n:::', '')
    return content


def insert_images_md(content, page_id):
    image_counter_pattern = r'\<!-- image (\d+) -->'
    matches = re.finditer(image_counter_pattern, content)

    for match in matches:
        original_text = match.group(0)
        image_counter = match.group(1)
        replacement = f"![]({base_url}images/page/{page_id}/Figure{image_counter}.png)"
        content = content.replace(original_text, replacement, 1)

    return content


def unescape_characters(md_content):
    escape_characters = r'\\([!"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~])'
    md_content = re.sub(escape_characters, r'\1', md_content)
    return md_content


def cleanup():
    os.remove(temp_tex)
    os.remove(temp_md)


def main():
    pull_en()
    
    Path(temp_md).touch(exist_ok=True)
    
    with open(src_dir + '/lkmpg.tex', 'r') as file:
        tex_content = file.read()
    
    tex_content = include_samplec(tex_content)
    tex_content = replace_code(tex_content)
    tex_content = replace_codebash(tex_content)
    tex_content = convert_verbatim_to_temp_tex(tex_content)
    tex_content = replace_image_references(tex_content)
    tex_content = replace_figures_with_captions(tex_content)

    with open(temp_tex, 'w+') as file:
        file.write(tex_content)
    
    cmd = f"cd {src_dir} & pandoc --wrap=none -s temp.tex -o ../temp.md"
    os.system(cmd)
    
    with open(temp_md, 'r') as file:
        md_content = file.read()
    
    md_content = add_section_numbers(md_content)
    
    populate_ref_dic(md_content)
    
    md_content = convert_section_references(md_content)
    md_content = convert_reference_labels(md_content)
    md_content = convert_refs(md_content)
    md_content = convert_urls(md_content)
    md_content = convert_verbatim_and_commands(md_content)
    md_content = remove_flushleft_md(md_content)
    md_content = unescape_characters(md_content)
    
    num_map = {}
    for number, name, url in chapters:
        num_map[number] = name
    
    page_map = get_page_map()
    for chapter_number in range(len(chapters)):
        page_id = page_map.get(str(chapter_number))
        splitted_content = md_content.split('\n# ', 1)
        with open(trg_dir + '/lkmpg' + str(chapter_number) + '.md', 'w') as file:
            chapter_content = insert_images_md(splitted_content[0], page_id)
            file.write(chapter_content)
        if len(splitted_content) > 1:
            md_content = splitted_content[1]
    
    shutil.copy(src_dir + '/README.md', 'lkmpg0.md')  # overwriting
    
    cleanup()


if __name__ == '__main__':
    main()
