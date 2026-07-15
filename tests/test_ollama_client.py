from backend.services.ollama_client import suggest_name


class TestSuggestName:
    def test_simple_path(self):
        assert suggest_name("/tmp/model.gguf") == "model"

    def test_strips_prefix(self):
        assert suggest_name("meta-llama_Llama-3.2-3B.gguf") == "llama-3.2-3b"

    def test_strips_mistral_prefix(self):
        assert suggest_name("Mistral_7B-v0.3.gguf") == "7b-v0.3"

    def test_strips_qwen_prefix(self):
        assert suggest_name("Qwen_Qwen2.5-7B.gguf") == "qwen2.5-7b"

    def test_removes_quant_suffix(self):
        assert suggest_name("model-q4_k_m.gguf") == "model"

    def test_removes_quant_with_dash(self):
        val = suggest_name("my-model-Q4_K_M.gguf")
        assert val == "my-model"

    def test_dot_gguf_stripped(self):
        assert suggest_name("test.gguf") == "test"

    def test_no_extension(self):
        assert suggest_name("test") == "test"

    def test_lowercase_conversion(self):
        assert suggest_name("MyModel.gguf") == "mymodel"

    def test_underscores_removed(self):
        assert suggest_name("my_model.gguf") == "mymodel"
