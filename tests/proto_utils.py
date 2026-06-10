import os
import shutil
import subprocess
import sys

def setup_mock_protos(tmp_path):
    """
    Creates the expected folder structure and 3 fixed proto files 
    (1 main and 2 nested custom sub-events) for testing compilation.
    """
    data_logs_dir = tmp_path / "data_logs"
    protos_dir = data_logs_dir / "protos"
    protos_dir.mkdir(parents=True)
    
    # Copy the actual script
    script_src = os.path.join(os.path.dirname(__file__), "..", "data_logs", "protos", "create_classes.py")
    script_dst = protos_dir / "create_classes.py"
    shutil.copy(script_src, script_dst)
    
    # Create 3 proto files (1 main, 2 nested custom)
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
    
    return data_logs_dir, protos_dir

def run_create_classes_script(protos_dir):
    """
    Executes the create_classes.py script inside the given directory.
    """
    result = subprocess.run(
        [sys.executable, "create_classes.py"],
        cwd=str(protos_dir),
        capture_output=True,
        text=True
    )
    return result

def verify_patched_imports(main_code):
    """
    Verifies that the regex correctly patched the recursive import 
    statements in the generated _pb2.py files.
    """
    # protoc normally generates: import sub_event1_pb2 as sub__event1__pb2
    # The script should patch it to: from . import sub_event1_pb2 as sub__event1__pb2
    assert "from . import sub_event1_pb2 as " in main_code, "Import patching failed for sub_event1"
    assert "from . import sub_event2_pb2 as " in main_code, "Import patching failed for sub_event2"
