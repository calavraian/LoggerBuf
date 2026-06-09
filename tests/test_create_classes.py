import os
import shutil
import subprocess
import pytest

@pytest.mark.proto
def test_create_classes_generates_and_patches_imports(tmp_path):
    """
    Tests that create_classes.py properly compiles 3 fixed proto files 
    (1 main and 2 custom sub-events) and patches the recursive import 
    statements in the generated _pb2.py files using regex.
    """
    # Create the expected folder structure
    data_logs_dir = tmp_path / "data_logs"
    protos_dir = data_logs_dir / "protos"
    protos_dir.mkdir(parents=True)
    
    # Copy the actual script
    script_src = os.path.join(os.path.dirname(__file__), "..", "data_logs", "protos", "create_classes.py")
    script_dst = protos_dir / "create_classes.py"
    shutil.copy(script_src, script_dst)
    
    # Create 3 proto files (fixed as requested: 1 main, 2 nested custom)
    main_proto = protos_dir / "main_data.proto"
    sub1_proto = protos_dir / "sub_event1.proto"
    sub2_proto = protos_dir / "sub_event2.proto"
    
    sub1_proto.write_text('syntax = "proto3";\nmessage SubEvent1 {\n  string val = 1;\n}\n')
    sub2_proto.write_text('syntax = "proto3";\nmessage SubEvent2 {\n  int32 num = 1;\n}\n')
    
    main_proto.write_text(
        'syntax = "proto3";\n'
        'import "sub_event1.proto";\n'
        'import "sub_event2.proto";\n'
        'message MainEvent {\n'
        '  SubEvent1 e1 = 1;\n'
        '  SubEvent2 e2 = 2;\n'
        '}\n'
    )
    
    # Run the script with cwd=protos_dir
    import sys
    result = subprocess.run(
        [sys.executable, "create_classes.py"],
        cwd=str(protos_dir),
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"create_classes.py failed: {result.stderr}"
    
    # Verify the generated files exist in the parent directory (data_logs)
    expected_files = [
        data_logs_dir / "main_data_pb2.py",
        data_logs_dir / "sub_event1_pb2.py",
        data_logs_dir / "sub_event2_pb2.py"
    ]
    
    for f in expected_files:
        assert f.exists(), f"Expected generated file {f.name} was not found"
        
    # Verify that the regex correctly patched the imports
    # In main_data_pb2.py we expect to find "from . import sub_event1_pb2 as ..."
    main_code = (data_logs_dir / "main_data_pb2.py").read_text()
    
    # protoc normally generates: import sub_event1_pb2 as sub__event1__pb2
    # The script should patch it to: from . import sub_event1_pb2 as sub__event1__pb2
    assert "from . import sub_event1_pb2 as " in main_code, "Import patching failed for sub_event1"
    assert "from . import sub_event2_pb2 as " in main_code, "Import patching failed for sub_event2"

