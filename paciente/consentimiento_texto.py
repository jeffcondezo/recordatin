"""
Texto digitalizado del consentimiento informado (transcripción del PDF oficial).

El PDF original (`consentimiento.pdf`) se sigue ofreciendo para lectura.
Este texto se usa para generar el PDF firmado dinámico.
"""

TITULO_ESTUDIO = (
    'Uso de una aplicación móvil de recordatorios y su asociación con la '
    'adherencia terapéutica en pacientes con enfermedades crónicas en el '
    'Hospital II EsSalud Huánuco, 2026'
)

INVESTIGADORES = [
    {
        'nombre': 'Carlos Alonso Ugarte Ríos',
        'cargo': 'Co-investigador',
        'institucion': (
            'Hospital II EsSalud Huánuco – '
            'Universidad Nacional Hermilio Valdizán'
        ),
        'telefono': '930361839',
        'dni': '72787314',
        'firma': 'firma_i1.png',
    },
    {
        'nombre': 'Jeff Carlos Peña Condezo',
        'cargo': 'Co-investigador',
        'institucion': (
            'Hospital II EsSalud Huánuco – '
            'Universidad Nacional Hermilio Valdizán'
        ),
        'telefono': '940009628',
        'dni': '70864821',
        'firma': 'firma_i2.png',
    },
]

# Bloques del documento (título, párrafos o listas).
# tipo: 'h1' | 'h2' | 'p' | 'ul'
SECCIONES_CONSENTIMIENTO = [
    {
        'tipo': 'h1',
        'texto': 'CONSENTIMIENTO INFORMADO',
    },
    {
        'tipo': 'p',
        'texto': f'«{TITULO_ESTUDIO}»',
    },
    {
        'tipo': 'h2',
        'texto': 'DECLARACIÓN',
    },
    {
        'tipo': 'p',
        'texto': (
            'Estimado participante, el presente documento forma parte del estudio '
            f'de investigación titulado «{TITULO_ESTUDIO}».'
        ),
    },
    {
        'tipo': 'p',
        'texto': (
            'Tiene como objetivo determinar el efecto de una estrategia basada en '
            'recordatorios móviles sobre el nivel de adherencia terapéutica en '
            'pacientes con diabetes mellitus tipo 2 e hipertensión arterial '
            'atendidos en el Hospital II EsSalud Huánuco durante el año 2026.'
        ),
    },
    {
        'tipo': 'p',
        'texto': (
            'El desarrollo del estudio comprende las etapas de recolección de '
            'información, implementación de la intervención, seguimiento y análisis '
            'estadístico de los resultados durante el periodo establecido en el '
            'protocolo de investigación.'
        ),
    },
    {
        'tipo': 'p',
        'texto': (
            'La información obtenida permitirá generar evidencia científica sobre '
            'el uso de tecnologías móviles para mejorar la adherencia al tratamiento '
            'farmacológico en pacientes con enfermedades crónicas, contribuyendo al '
            'desarrollo de estrategias que fortalezcan el autocuidado y la continuidad '
            'del tratamiento en beneficio de futuros pacientes.'
        ),
    },
    {
        'tipo': 'p',
        'texto': (
            'La participación consistirá en responder el cuestionario Morisky '
            'Medication Adherence Scale de 8 ítems (MMAS-8), proporcionar algunos '
            'datos generales relacionados con su tratamiento y, si pertenece al '
            'grupo de intervención, utilizar una aplicación móvil de recordatorios '
            'durante ocho semanas. Asimismo, se registrará de forma automática el '
            'uso de la aplicación (frecuencia de apertura y confirmación de '
            'recordatorios). La duración aproximada de cada evaluación será de '
            '5 a 10 minutos.'
        ),
    },
    {
        'tipo': 'h2',
        'texto': 'EQUIPO DE INVESTIGACIÓN',
    },
    {
        'tipo': 'p',
        'texto': (
            'El equipo de investigación responsable de la ejecución del protocolo '
            'está integrado por:'
        ),
    },
    {
        'tipo': 'ul',
        'items': [
            (
                'Carlos Alonso Ugarte Ríos — Co-investigador — '
                'Hospital II EsSalud Huánuco – Universidad Nacional Hermilio Valdizán '
                '— Tel. 930361839 — DNI 72787314'
            ),
            (
                'Jeff Carlos Peña Condezo — Co-investigador — '
                'Hospital II EsSalud Huánuco – Universidad Nacional Hermilio Valdizán '
                '— Tel. 940009628 — DNI 70864821'
            ),
        ],
    },
    {
        'tipo': 'h2',
        'texto': 'PARTICIPACIÓN Y PROCEDIMIENTOS',
    },
    {
        'tipo': 'p',
        'texto': 'Si usted acepta participar:',
    },
    {
        'tipo': 'ul',
        'items': [
            'Se verificará que cumpla los criterios de inclusión del estudio.',
            'Se le solicitará firmar este consentimiento informado.',
            'Se aplicará el cuestionario MMAS-8 antes del inicio del estudio.',
            (
                'Si corresponde al grupo de intervención, se instalará la aplicación '
                'móvil de recordatorios en su teléfono celular y se le enseñará su uso.'
            ),
            (
                'Durante ocho semanas continuará con su tratamiento habitual; la '
                'aplicación únicamente enviará recordatorios para la toma de medicamentos.'
            ),
            (
                'Al finalizar el seguimiento se volverá a aplicar el cuestionario '
                'MMAS-8 para evaluar los resultados.'
            ),
        ],
    },
    {
        'tipo': 'h2',
        'texto': 'RIESGOS / INCOMODIDADES',
    },
    {
        'tipo': 'p',
        'texto': (
            'Esta investigación representa riesgo mínimo. No se realizarán '
            'procedimientos invasivos, extracción de sangre ni modificaciones de '
            'su tratamiento médico habitual. Como posible incomodidad, podría '
            'requerirse tiempo para responder el cuestionario o para aprender el '
            'funcionamiento de la aplicación móvil.'
        ),
    },
    {
        'tipo': 'h2',
        'texto': 'BENEFICIOS PARA EL PARTICIPANTE',
    },
    {
        'tipo': 'p',
        'texto': 'Su participación podría favorecer:',
    },
    {
        'tipo': 'ul',
        'items': [
            'Mejor organización de la toma de sus medicamentos.',
            'Disminución del olvido de las dosis prescritas.',
            'Mayor conocimiento sobre la importancia del cumplimiento del tratamiento.',
            (
                'Contribución al desarrollo de estrategias tecnológicas que '
                'beneficien a otros pacientes con enfermedades crónicas.'
            ),
        ],
    },
    {
        'tipo': 'p',
        'texto': 'No se garantiza un beneficio clínico directo para todos los participantes.',
    },
    {
        'tipo': 'h2',
        'texto': 'NIVEL / CALIDAD DE ATENCIÓN',
    },
    {
        'tipo': 'p',
        'texto': (
            'Su decisión de participar o no participar no afectará de ninguna manera '
            'la atención médica que recibe en el Hospital II EsSalud Huánuco. Continuará '
            'recibiendo los mismos servicios y tratamiento independientemente de su decisión.'
        ),
    },
    {
        'tipo': 'h2',
        'texto': 'ALTERNATIVAS DE DIAGNÓSTICO / TRATAMIENTO',
    },
    {
        'tipo': 'p',
        'texto': (
            'La participación en este estudio no reemplaza ni modifica el tratamiento '
            'indicado por su médico tratante. En caso de no participar, continuará '
            'recibiendo el tratamiento convencional establecido por el Hospital II '
            'EsSalud Huánuco.'
        ),
    },
    {
        'tipo': 'h2',
        'texto': 'CONFIDENCIALIDAD DE LA INFORMACIÓN',
    },
    {
        'tipo': 'p',
        'texto': (
            'Toda la información obtenida será estrictamente confidencial. Los datos '
            'personales serán codificados mediante un número de identificación, '
            'evitando que usted pueda ser identificado en publicaciones o informes '
            'científicos. La información será utilizada únicamente con fines académicos '
            'y científicos. Los registros digitales generados por la aplicación serán '
            'almacenados en servidores protegidos y únicamente tendrán acceso los '
            'investigadores autorizados.'
        ),
    },
    {
        'tipo': 'h2',
        'texto': 'ATENCIÓN EN CASO DE CONSULTAS',
    },
    {
        'tipo': 'p',
        'texto': (
            'Los investigadores estarán disponibles para resolver cualquier duda '
            'relacionada con la investigación durante todo el desarrollo del estudio. '
            'Si durante el estudio se presenta alguna situación relacionada con la '
            'investigación, recibirá la orientación correspondiente por parte del '
            'equipo investigador.'
        ),
    },
    {
        'tipo': 'h2',
        'texto': 'PREGUNTAS O PROBLEMAS',
    },
    {
        'tipo': 'p',
        'texto': (
            'Si tiene preguntas, comentarios o desea retirar su consentimiento en '
            'cualquier momento, podrá comunicarse con cualquiera de los investigadores '
            'del proyecto:'
        ),
    },
    {
        'tipo': 'ul',
        'items': [
            'Carlos Alonso Ugarte Ríos',
            'Jeff Carlos Peña Condezo',
        ],
    },
    {
        'tipo': 'p',
        'texto': (
            'Los números telefónicos y correos electrónicos institucionales serán '
            'consignados antes de la aplicación del consentimiento informado. También '
            'podrá comunicarse con el Comité de Ética en Investigación del Hospital II '
            'EsSalud Huánuco para resolver cualquier inquietud relacionada con sus '
            'derechos como participante.'
        ),
    },
    {
        'tipo': 'h2',
        'texto': 'CONSENTIMIENTO / PARTICIPACIÓN VOLUNTARIA',
    },
    {
        'tipo': 'p',
        'texto': 'He leído o se me ha explicado el contenido del presente documento.',
    },
    {
        'tipo': 'p',
        'texto': (
            'He tenido la oportunidad de formular preguntas y todas han sido '
            'respondidas satisfactoriamente.'
        ),
    },
    {
        'tipo': 'p',
        'texto': (
            'Comprendo que mi participación es completamente voluntaria y que puedo '
            'retirarme del estudio en cualquier momento, sin necesidad de brindar '
            'explicación alguna y sin que ello afecte la atención médica que recibo.'
        ),
    },
    {
        'tipo': 'p',
        'texto': (
            'Por lo tanto, ACEPTO PARTICIPAR voluntariamente en el estudio de '
            f'investigación denominado: «{TITULO_ESTUDIO}».'
        ),
    },
]
