from pathlib import Path
from dataclasses import dataclass
from omegaconf import OmegaConf

#方法一
# config_file =Path(__file__).parents[2]/'conf'/'text_config.yaml'
# conf = OmegaConf.load(config_file)
# print(conf['name'])

#方法二
@dataclass
class FileConfig:
    enable: bool
    level: str


# 定义封装实体
@dataclass
class AppConfig:
    name: str
    age: int
    height: float
    file: FileConfig

config_file = Path(__file__).parents[2]/'conf'/'text_config.yaml'
content = OmegaConf.load(config_file)
schema = OmegaConf.structured(AppConfig)
app_config:AppConfig = OmegaConf.to_object(OmegaConf.merge(schema, content))
print(app_config.name)