from __future__ import annotations
from collections.abc import Callable

import importlib
import logging
import re
import os



def is_valid_python_module_name(p_name: str) -> bool:
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", p_name) != None



class Component:
    def __init__(self):
        self.name: str = ""
        self.render_callback: Callable = None


class HTMLRenderer:
    logger: logging.Logger = logging.getLogger("RenderingEngine")
    logger.setLevel(logging.DEBUG)


    def __init__(self) -> None:
        self.components: list[Component] = []
    

    def component(self, p_name: str) -> Callable:

        def definition_wrapper(p_decorated_function: Callable) -> Callable:

            def call_wrapper(p_args: dict[str, str]) -> str:
                return p_decorated_function(p_args)

            self.register_component(p_name, call_wrapper)

            return call_wrapper

        return definition_wrapper


    def render(self, p_source: str, p_paste_keys: dict[str, str]={}) -> str:
        rendered_source: str = p_source

        # NOTE(vanya): Replace all component syntax with registered components until none are lefr
        while True:
            # NOTE(vanya): Match component syntax
            component_regex_match = re.search(r"\{\{.*?\}\}", rendered_source)
            
            if component_regex_match == None:
                # NOTE(vanya): No components left to replace
                break
            
            replace_str: str = ""

            # NOTE(vanya): Parse component syntax
            component_syntax: str = component_regex_match.group(0)
            component_inner_syntax: str = component_syntax.removeprefix("{{").removesuffix("}}").strip()

            args = dict(re.findall(r'(\w+)="([^"]*)"', component_inner_syntax))

            requested_component_name: str = component_inner_syntax.split(None, 1)[0]

            if not requested_component_name:
                self.logger.warning(f"Component syntax without a component name! `{component_syntax}` `{requested_component_name}`")

            # NOTE(vanya): Search for a component to render the replacement
            found_requested_component: bool = False
            for component in self.components:
                if component.name == requested_component_name:
                    # NOTE(vanya): Call component rendering function with argments and renderpass parameters
                    replace_str = component.render_callback(args)

                    found_requested_component = True
                    break
            
            if not found_requested_component:
                if requested_component_name in p_paste_keys:
                    replace_str = str(p_paste_keys[requested_component_name])
                else:
                    self.logger.error(f"Could not find a requested component `{requested_component_name}`.")

            # NOTE(vanya): Replace HTML source
            rendered_source = rendered_source[:component_regex_match.start()] + replace_str + rendered_source[component_regex_match.end():]

        return rendered_source
    

    def render_file(self, p_path: str, p_paste_keys: dict[str, str]={}) -> str:
        with open(p_path, "r", encoding="utf-8") as f:
            return self.render(f.read(), p_paste_keys)
    

    def register_component(self, p_name: str, p_render_callback: Callable) -> None:
        new_component = Component()
        new_component.name = p_name
        new_component.render_callback = p_render_callback

        self.components.append(new_component)

        self.logger.debug(f"Registered component `{p_name}`")


    def register_components_from_dir(self, p_path: str) -> None:
        self.logger.debug(f"Scanning directory `{p_path}` to register components.")

        for p_dir_path, p_dir_names, p_file_names in os.walk(p_path):
            for file_name in p_file_names:
                file_path: str = os.path.join(p_dir_path, file_name)

                if os.path.isfile(file_path):
                    if file_name.endswith(".py"):
                        self.logger.debug(f"Found `{file_path}` - Attempting to import and call `register_components(app)`")
                        
                        project_root_path: str = os.path.abspath(os.getcwd())

                        if not os.path.abspath(file_path).startswith(project_root_path):
                            self.logger.warning(f"{file_path} is not in the same directory (or any of its children directories) and the project root - cannot import the module.")
                            continue
                        
                        module_path: str = \
                            os.path.relpath(file_path, project_root_path) \
                            .replace(os.sep, ".") \
                            .removesuffix(".py")
                        
                        module_path_has_illegal_characters: bool = False
                        for module_path_part in module_path.split("."):
                            if not is_valid_python_module_name(module_path_part):
                                module_path_has_illegal_characters = True
                                break
                        
                        if module_path_has_illegal_characters:
                            self.logger.warning(f"Module path `{module_path}` has illegal characters. (Each part can only have A-Z, 0-9, and underscores. And must not begin with a number)")
                            continue

                        component_registrar_module = importlib.import_module(module_path)
                        
                        if hasattr(component_registrar_module, "register_components"):
                            component_registrar_module.register_components(self)
                        else:
                            self.logger.error(f"Module `{module_path}` has no function `register_components(html_renderer)` which usually registers the components.")
                    
                    elif file_path.endswith(".html"):
                        def simple_html_render_callback(p_args: dict, p_file_path: str=file_path) -> str:
                            return self.render_file(p_file_path, {})

                        self.register_component(file_path.removeprefix(p_path).removeprefix(os.sep), simple_html_render_callback)



class HTML:
    def __init__(self):
        self.parent: HTML|None = None
        self.children: list[HTML|str] = []
        self.name: str = ""
        self.attributes: dict = {}
    

    def push_element(self, p_name: str, p_content: HTML|str|None=None, **p_html_attrs) -> HTML:
        e = HTML()
        e.name = p_name

        # NOTE(vanya): Assign content
        if p_content is not None:
            e.children.append(p_content)

        # NOTE(vanya): Assign parent
        e.parent = self
        self.children.append(e)

        # NOTE(vanya): Assign attributes
        for key, value in p_html_attrs.items():
            if key == "class_":
                e.attributes["class"] = value
            elif key == "id_":
                e.attributes["id"] = value
            else:
                e.attributes[key] = value

        return e


    def render_html(self) -> str:
        # NOTE(vanya): Stringify the attributes
        attribute_source: str = ""

        for key, value in self.attributes.items():
            attribute_source += f" {key}=\"{value}\""

        # NOTE(vanya): Render children (Potentially recursive)
        inner_html: str = ""

        for child in self.children:
            if isinstance(child, str):
                inner_html += child
            
            if isinstance(child, HTML):
                inner_html += child.render_html()

        return f"<{self.name}{attribute_source}>{inner_html}</{self.name}>"
