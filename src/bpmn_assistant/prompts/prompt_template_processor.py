import os

from jinja2 import Environment, FileSystemLoader, select_autoescape


class PromptTemplateProcessor:
    def __init__(self, prompts_dir=os.path.dirname(os.path.abspath(__file__))):
        """
        Initialize the template processor with a directory containing prompt templates.

        Args:
            prompts_dir (str): Path to the directory containing prompt templates
        """
        self.env = Environment(
            loader=FileSystemLoader(prompts_dir),
            autoescape=select_autoescape(),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_template(self, template_name, **kwargs):
        """
        Render a template with the provided variables.

        Args:
            template_name (str): Name of the template file
            **kwargs: Variables to pass to the template

        Returns:
            str: Rendered template string
        """
        template = self.env.get_template(template_name)
        return template.render(**kwargs)
