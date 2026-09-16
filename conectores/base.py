# -*- coding: utf-8 -*-
"""
Interface comum que todo conector de indicador deve implementar.

Para adicionar um novo indicador no futuro (CDI, Selic, Ibovespa, etc.):
  1. Crie um arquivo novo em conectores/ (ex.: conectores/selic.py).
  2. Implemente uma classe que herda de Conector e retorna um Leitura.
  3. Registre a classe em nucleo/motor.py, no dicionário CONECTORES.
  4. Adicione o indicador em config/indicadores.yaml.
Nenhuma outra parte do sistema precisa ser alterada.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class Leitura:
    """Resultado de uma consulta a um indicador, pronto para comparar e exibir."""

    valor: float                          # valor numérico comparável ao gatilho
    valor_formatado: str                  # como mostrar no e-mail (ex.: "R$ 5,08")
    variacao: Optional[float] = None      # variação numérica (dia ou vs. leitura anterior)
    variacao_sufixo: str = "%"            # sufixo mostrado junto da variação
    fonte: str = ""                       # nome da fonte, para exibir no e-mail/log
    data_base: str = ""                   # data de referência do dado, se aplicável
    detalhes: List[Tuple[str, str]] = field(default_factory=list)  # linhas extras no e-mail


class Conector(ABC):
    """Todo indicador (dólar, título do Tesouro, futuro CDI, etc.) implementa esta interface."""

    @abstractmethod
    def consultar(self, parametros: dict) -> Optional[Leitura]:
        """
        Busca o valor atual na fonte.

        Deve levantar uma exceção (RuntimeError, por exemplo) se a fonte
        estiver indisponível — o motor principal trata isso como erro de
        consulta e NÃO interpreta como gatilho atingido. Deve retornar None
        (sem levantar exceção) apenas quando a fonte respondeu normalmente,
        mas o dado pedido não existe nela (ex.: título sem oferta no dia).
        """
        raise NotImplementedError
