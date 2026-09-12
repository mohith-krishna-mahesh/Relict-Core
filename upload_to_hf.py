from huggingface_hub import HfApi

repo_id = "MaestroS231/relict-core-objective-resolution-qlora"

api = HfApi()
api.upload_folder(
    folder_path="app/core_model/training/checkpoints/objective_resolution_qlora",
    repo_id=repo_id,
    repo_type="model",
    allow_patterns=[
        "adapter_config.json",
        "adapter_model.safetensors",
        "tokenizer*",
        "chat_template.jinja",
        "README.md",
    ],
)

print(f"Upload complete: https://huggingface.co/{repo_id}")