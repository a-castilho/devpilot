# Isolamento de imagens anexadas a tarefas

As imagens temporárias usadas pelo Codex são recursos tenant-scoped. O identificador aleatório do arquivo reduz colisões, mas não substitui autorização.

## Invariantes

- Upload e exclusão usam exclusivamente o `workspace_id` do principal autenticado.
- Os arquivos ficam em `data/task-images/<workspace_id>/<image_id>`; nomes de workspace com sintaxe de caminho são rejeitados.
- O marker público continua no formato `[DEVPILOT_IMAGE=<image_id>]`, sem expor o workspace.
- Ao executar uma tarefa, o DevPilot resolve o marker somente dentro do `workspace_id` do projeto persistido.
- Um marker válido de outro workspace é tratado como imagem ausente; o executor não procura no diretório global nem em outros tenants.
- Imagens legadas armazenadas diretamente em `data/task-images/` não são migradas automaticamente, porque não existe metadado confiável que permita atribuí-las a um tenant. O comportamento é fail-closed.

## Compatibilidade e limpeza

Não há migration de banco nem mudança no payload do frontend. Novos uploads passam a usar a estrutura tenant-scoped imediatamente. Arquivos legados podem ser removidos posteriormente por housekeeping explícito após confirmação de que não existem tarefas ativas que dependam deles.

## Testes de regressão

`tests/test_task_images.py` cobre resolução no workspace do projeto e bloqueio de marker estrangeiro. `tests/test_task_image_workspace_routes.py` cobre upload e exclusão com o workspace autenticado.
