import pytest
from .proto_utils import setup_mock_protos, run_create_classes_script, verify_patched_imports

@pytest.mark.proto
def test_create_classes_generates_and_patches_imports(tmp_path):
    """
    Tests that create_classes.py properly compiles 3 fixed proto files 
    (1 main and 2 custom sub-events) and patches the recursive import 
    statements in the generated _pb2.py files using regex.
    """
    # 1. Setup mock environment
    data_logs_dir, protos_dir = setup_mock_protos(tmp_path)
    
    # 2. Execute script
    result = run_create_classes_script(protos_dir)
    assert result.returncode == 0, f"create_classes.py failed: {result.stderr}"
    
    # 3. Verify generation
    expected_files = [
        data_logs_dir / "main_data_pb2.py",
        data_logs_dir / "sub_event1_pb2.py",
        data_logs_dir / "sub_event2_pb2.py"
    ]
    for f in expected_files:
        assert f.exists(), f"Expected generated file {f.name} was not found"
        
    # 4. Verify regex patching
    main_code = (data_logs_dir / "main_data_pb2.py").read_text()
    verify_patched_imports(main_code)

