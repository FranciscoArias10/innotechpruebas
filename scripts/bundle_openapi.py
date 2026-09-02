#!/usr/bin/env python3
import glob
import os
import yaml

def bundle_openapi():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    openapi_dir = os.path.join(base_dir, 'openapi')
    
    yaml_files = sorted(glob.glob(os.path.join(openapi_dir, '*.yaml')))
    
    combined = {
        "openapi": "3.0.3",
        "info": {
            "title": "SIGE-UBE — API móvil",
            "version": "1.0.0",
            "description": "Especificación completa de la API Móvil SIGE-UBE (12 módulos)."
        },
        "servers": [
            {"url": "https://sige.innotech-solutions.com.ec/api/v1.0.0", "description": "Staging (datos sintéticos)"},
            {"url": "http://localhost:8000/api/v1.0.0", "description": "Servidor Local"}
        ],
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT"
                }
            },
            "schemas": {},
            "parameters": {}
        },
        "paths": {}
    }
    
    ignore_files = {'openapi.yaml', 'combined.yaml', 'bundle.yaml'}
    
    for filepath in yaml_files:
        filename = os.path.basename(filepath)
        if filename in ignore_files:
            continue
            
        with open(filepath, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
            
        if not spec or not isinstance(spec, dict):
            continue
            
        # Merge paths
        paths = spec.get('paths', {})
        for path, path_item in paths.items():
            if path in combined['paths']:
                combined['paths'][path].update(path_item)
            else:
                combined['paths'][path] = path_item
                
        # Merge components
        components = spec.get('components', {})
        schemas = components.get('schemas', {})
        for schema_name, schema_body in schemas.items():
            if schema_name not in combined['components']['schemas']:
                combined['components']['schemas'][schema_name] = schema_body
                
        params = components.get('parameters', {})
        for param_name, param_body in params.items():
            if param_name not in combined['components']['parameters']:
                combined['components']['parameters'][param_name] = param_body
                
    output_path = os.path.join(openapi_dir, 'openapi.yaml')
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(combined, f, sort_keys=False, allow_unicode=True)
        
    print(f"Bundled {len(combined['paths'])} paths into {output_path}")

if __name__ == '__main__':
    bundle_openapi()
