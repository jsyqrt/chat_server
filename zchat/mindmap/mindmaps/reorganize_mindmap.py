import json
import uuid
import re
import os
from zchat.apis.llm import get_response_from_llm, get_json_blocks_from_llm_response
import yaml

class AllMindmapLoader:
    def __init__(self, directory = "/Users/liuqian/mycode/github/sf/archive/developer-roadmap/public/roadmap-content"):
        self.directory = directory

        self.keyword_to_id = {}
        self.id_to_detail = {}
        self.map_name_to_id_list = {}

        self.load_all_mindmaps()

    def load_all_mindmaps(self):
        for file in os.listdir(self.directory):
            if file.endswith(".json"):
                with open(os.path.join(self.directory, file), "r") as f:
                    map_name = file.split(".")[0]
                    id_list = []

                    mindmap = json.load(f)
                    for item in mindmap.items():
                        id = item[0]
                        detail = item[1]
                        detail['xid'] = id
                        title = detail['title']
                        self.keyword_to_id[title] = id
                        self.id_to_detail[id] = detail
                        id_list.append(id)

                    self.map_name_to_id_list[map_name] = id_list

    def get_detail_by_id(self, id):
        return self.id_to_detail.get(id, {})

    def get_detail_by_keyword(self, keyword):
        return self.id_to_detail.get(self.keyword_to_id.get(keyword, ""), {})

class ReorganizeMindmap:
    JSON_SCHEMA = """
Your output needs to conform to the following JSON format:

```json
{
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "node title"
        },
        "children": {
            "type": "array",
            "items": {
                "$ref": "#/definitions/node"
            },
            "description": "sub-node list"
        }
    },
    "required": [
        "title",
        "children"
    ],
    "definitions": {
        "node": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "node title"
                },
                "children": {
                    "type": "array",
                    "items": {
                        "$ref": "#/definitions/node"
                    },
                    "description": "sub-node list"
                }
            },
            "required": [
                "title"
            ]
        }
    }
}
```
"""

    def __init__(self, filename, all_mindmap_loader):
        self.json_filename = filename
        self.all_mindmap_loader = all_mindmap_loader

    def generate_uid(self):
        return str(uuid.uuid4())

    def reorganize(self):
        with open(self.json_filename, "r") as f:
            mindmap = json.load(f)

        new_mindmap = self.update_node_in_map(mindmap)
        return new_mindmap

    def update_node_in_map(self, map):
        updated_map = map
        updated_map['id'] = self.generate_uid()
        updated_map['done'] = False

        detail = self.all_mindmap_loader.get_detail_by_keyword(map['title'])
        updated_map['description'] = map.get('description', detail.get('description', map['title']))
        updated_map['description'] = updated_map['description'].replace("Visit the following resources to learn more:", "")
        updated_map['links'] = detail.get('links', [])

        children = map.get('children', [])
        if children:
            new_children = []
            for item in children:
                if isinstance(item, dict):
                    new_children.append(self.update_node_in_map(item))
            updated_map['children'] = new_children

        return updated_map

class MindmapFromFiles:
    def __init__(self, directory, all_mindmap_loader):
        self.directory = directory
        self.all_mindmap_loader = all_mindmap_loader

        self.mindmap_name = os.path.basename(self.directory)
        self.migration_filename = os.path.join(self.directory, 'migration-mapping.json')
        self.markdown_filename = os.path.join(self.directory, f'{self.mindmap_name}.md')

        with open(self.migration_filename, "r") as f:
            self.migration_json = json.load(f)

        with open(self.markdown_filename, "r") as f:
            self.markdown_content = f.read()

        self.header_info = self.extract_markdown_header_info(self.markdown_content)

    def extract_markdown_header_info(self, markdown_content):
        """
        Extract title, question.title, and question.description from a markdown file with YAML frontmatter.

        Args:
            markdown_content (str): The content of the markdown file

        Returns:
            dict: A dictionary containing the extracted information
        """
        # Find the YAML frontmatter between --- markers
        yaml_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL | re.MULTILINE)
        yaml_match = yaml_pattern.search(markdown_content)

        if not yaml_match:
            return {"error": "No YAML frontmatter found"}

        yaml_content = yaml_match.group(1)

        try:
            # Parse the YAML content
            header_data = yaml.safe_load(yaml_content)

            # Extract the required fields
            result = {
                "title": header_data.get("title", ""),
                "question_title": header_data.get("question", {}).get("title", ""),
                "question_description": header_data.get("question", {}).get("description", ""),
                "description": header_data.get("description", "")
            }

            return result

        except yaml.YAMLError as e:
            return {"error": f"Failed to parse YAML: {str(e)}"}

    def get_mindmap(self):
        # 初始化结果字典
        result = {
          "id": str(uuid.uuid4()),
          "title": self.header_info.get("title", ""),
          "description": self.header_info.get('description', ''),
          "question_title": self.header_info.get('question_title', ''),
          "question_description": self.header_info.get('question_description', ''),
          "children": [],
          "links": [],
        }

        # 创建一个字典来存储所有节点的引用
        nodes_dict = {}

        # 第一遍：创建所有根节点
        for key, value in self.migration_json.items():
            parts = key.split(":")
            root = parts[0]

            # 如果根节点还不存在，创建它
            if root not in nodes_dict:
                xid = self.migration_json.get(root, "")
                detail = self.all_mindmap_loader.get_detail_by_id(xid)
                title = detail.get('title', root)
                description = detail.get('description', root)
                description = description.replace("Visit the following resources to learn more:", "")
                description = description.replace("Learn more from the following links:", "")
                description = description.replace("Learn more from the following resources:", "")
                links = detail.get('links', [])
                id = str(uuid.uuid4())
                node = {"title": title, "xid": xid, "description": description, "id": id, "children": [], "links": links}
                nodes_dict[root] = node
                result["children"].append(node)

        # 第二遍：添加所有子节点
        for key, value in self.migration_json.items():
            parts = key.split(":")

            # 跳过只有一层的键
            if len(parts) == 1:
                continue

            # 找到当前路径的父节点
            current_path = parts[0]
            parent_node = nodes_dict[current_path]

            # 遍历路径中的每个部分（除了第一个和最后一个）
            for i in range(1, len(parts) - 1):
                current_path += ":" + parts[i]

                # 如果当前路径还不存在，创建它
                if current_path not in nodes_dict:
                    xid = self.migration_json.get(current_path, "")
                    detail = self.all_mindmap_loader.get_detail_by_id(xid)
                    title = detail.get('title', parts[i])
                    description = detail.get('description', parts[i])
                    description = description.replace("Visit the following resources to learn more:", "")
                    description = description.replace("Learn more from the following links:", "")
                    description = description.replace("Learn more from the following resources:", "")
                    links = detail.get('links', [])
                    id = str(uuid.uuid4())
                    node = {"title": title, "xid": xid, "description": description, "id": id, "children": [], "links": links}
                    nodes_dict[current_path] = node
                    parent_node["children"].append(node)

                parent_node = nodes_dict[current_path]

            # 添加最后一个节点
            last_part = parts[-1]
            current_path += ":" + last_part

            # 如果最后一个节点还不存在，创建它
            if current_path not in nodes_dict:
                xid = value
                detail = self.all_mindmap_loader.get_detail_by_id(xid)
                title = detail.get('title', last_part)
                description = detail.get('description', last_part)
                description = description.replace("Visit the following resources to learn more:", "")
                description = description.replace("Learn more from the following links:", "")
                description = description.replace("Learn more from the following resources:", "")
                links = detail.get('links', [])
                id = str(uuid.uuid4())
                node = {"title": title, "xid": xid, "description": description, "id": id, "children": [], "links": links}
                nodes_dict[current_path] = node
                parent_node["children"].append(node)

        return result

    def translate_mindmap(self, mindmap):
        mindmap_to_translate = {
          "title": mindmap['title'],
          "description": mindmap['description'],
          "links": mindmap['links'],
        }

        if mindmap.get('question_title', None):
          mindmap_to_translate['question_title'] = mindmap['question_title']

        if mindmap.get('question_description', None):
          mindmap_to_translate['question_description'] = mindmap['question_description']

        mindmap_to_translate_json = json.dumps(mindmap_to_translate, indent=2)

        system_prompt = """
你是一个专业的翻译，擅长将英文翻译为中文，尤其是在保持专业术语的准确性，以及保持JSON格式方面。
在翻译专业术语时，对于首次翻译，提供中文翻译并在括号内注明术语原文。
在整个翻译中，对术语的翻译要连贯一致，不要出现同一个术语在不同的地方翻译不同的情况。
翻译title，description的内容，如果字段存在时，翻译question_title，question_description的内容。
翻译links中的title的内容。但保持links中的url和type的内容不变。
保持JSON的格式不变。
"""

        user_prompt = f"""
```json
翻译下面的JSON：
{mindmap_to_translate_json}
```
输出相同格式的JSON：
"""
        messages = [
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": user_prompt},
        ]

        try_count = 0
        while try_count < 3:
            try_count += 1
            try:
                response = get_response_from_llm(messages, "qwen-2.5-32b", 32768)
                # response = get_response_from_llm(messages, "deepseek-chat", 8192, platform='deepseek')
                json_blocks = get_json_blocks_from_llm_response(response)
                new_mindmap = json.loads(json_blocks[0])
                print(new_mindmap)
                break
            except Exception as e:
                print(f"error: {e}")

        if try_count >= 3:
            print('!!!!!!!! Failed to translate !!!!!!!!!! for json:')
            print(mindmap_to_translate_json)

        new_children = []
        for child in mindmap['children']:
            new_child = self.translate_mindmap(child)
            new_children.append(new_child)
        new_mindmap['children'] = new_children

        new_mindmap['id'] = str(uuid.uuid4())
        new_mindmap['xid'] = mindmap['id']

        return new_mindmap

if __name__ == "__main__":
    # all_mindmap_loader = AllMindmapLoader()
    # filename = "/Users/liuqian/mycode/github/sf/be/chat_server/zchat/mindmap/mindmaps/backend_png_gpt4o.json"
    # reorganizer = ReorganizeMindmap(filename=filename, all_mindmap_loader=all_mindmap_loader)
    # new_mindmap = reorganizer.reorganize()
    # print(json.dumps(new_mindmap, indent=2))

    all_mindmap_loader = AllMindmapLoader()
    base_dir = "/Users/liuqian/mycode/github/sf/archive/developer-roadmap/src/data/roadmaps"
    result_dir = "/Users/liuqian/mycode/github/sf/be/chat_server/zchat/mindmap/mindmaps"
    # for directory in os.listdir(base_dir):
    for directory in [
      # "backend",
      ]:
        if os.path.isdir(os.path.join(base_dir, directory)):
            if os.path.exists(os.path.join(base_dir, directory, "migration-mapping.json")):
                mindmap_from_files = MindmapFromFiles(os.path.join(base_dir, directory), all_mindmap_loader)

                mindmap_en = mindmap_from_files.get_mindmap()

                # 生成原始mindmap
                json_str_result = json.dumps(mindmap_en, indent=2)
                with open(os.path.join(result_dir, f"{directory}.json"), "w") as f:
                    print(f"writing {directory}.json")
                    f.write(json_str_result)

                # 生成翻译后的mindmap
                mindmap_cn = mindmap_from_files.translate_mindmap(mindmap_en)
                json_str_result = json.dumps(mindmap_cn, indent=2, ensure_ascii=False).replace("。", "。\n\n").replace("\n\n\n\n", "\n\n")
                with open(os.path.join(result_dir, f"{directory}_cn.json"), "w") as f:
                    print(f"writing {directory}_cn.json")
                    f.write(json_str_result)
