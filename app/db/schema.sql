-- =============================================================================
-- 广州小升初密考模拟系统 · SQLite Schema
-- =============================================================================
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- 知识点：从 data/knowledge_graph.yaml 同步而来
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_nodes (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    module          TEXT NOT NULL,               -- number_algebra / fraction_percent / travel / geometry / ratio_proportion / misc_comprehensive
    difficulty      INTEGER NOT NULL DEFAULT 2,  -- 1..5
    frequency       TEXT NOT NULL DEFAULT 'mid', -- high / mid / low
    points          TEXT NOT NULL DEFAULT '[]',  -- JSON 数组，细分命题点
    slots           TEXT NOT NULL DEFAULT '[]',  -- JSON 数组，适用题型
    updated_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 知识点的前置依赖，构成"知识链"
CREATE TABLE IF NOT EXISTS knowledge_prereq (
    node_id     TEXT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    prereq_id   TEXT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, prereq_id)
);
CREATE INDEX IF NOT EXISTS idx_prereq_node ON knowledge_prereq(node_id);

-- -----------------------------------------------------------------------------
-- 题目：
--   固定题  — params 为 NULL，stem 即最终题干
--   参数化题 — params 为 JSON，定义变量取值空间；
--             stem/solution/answer 中可用 {{var}} 占位，
--             answer_expr 是 Python 表达式，代入变量后由代码算出最终答案
--             （答案永不由大模型生成，保证 100% 正确）
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS questions (
    id              TEXT PRIMARY KEY,
    knowledge_id    TEXT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE RESTRICT,
    slot            TEXT NOT NULL,               -- fill / choice / judge / calc / geometry / solve / extra
    stem            TEXT NOT NULL,               -- 题干，含 {{var}} 占位符
    answer_expr     TEXT NOT NULL,               -- 答案 Python 表达式，形如 "{a}*{b}" 或 "round({v},2)"
    answer_display  TEXT,                        -- 答案展示模板（None 则直接用计算结果）
    solution        TEXT,                        -- 解题思路，含 {{var}}
    figure_svg      TEXT,                        -- SVG 图形（可选，支持 {{var}}）
    choices_expr    TEXT,                        -- 选择题：JSON 字符串，四个选项，其一为正确答案，形如 ["{a}","{a_plus}","{wrong1}","{wrong2}"]
    params          TEXT,                        -- JSON 参数空间，NULL 表示固定题
    unit            TEXT,                        -- 单位
    difficulty      INTEGER,
    source          TEXT NOT NULL DEFAULT 'original',  -- original（原创仿真）/ user_input（用户录入）
    enabled         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_q_knowledge ON questions(knowledge_id);
CREATE INDEX IF NOT EXISTS idx_q_slot ON questions(slot);

-- -----------------------------------------------------------------------------
-- 试卷
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS papers (
    id              TEXT PRIMARY KEY,            -- UUID
    title           TEXT NOT NULL,
    seed            INTEGER NOT NULL,            -- 随机种子，同种子可复现同一套卷
    total_score     INTEGER NOT NULL DEFAULT 100,
    duration_min    INTEGER NOT NULL DEFAULT 100,
    status          TEXT NOT NULL DEFAULT 'draft',   -- draft / checked / published
    check_report    TEXT,                        -- JSON，出卷体检报告
    created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS paper_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    seq             INTEGER NOT NULL,            -- 卷面序号，从 1 开始
    slot            TEXT NOT NULL,
    section_title   TEXT NOT NULL,
    section_instruction TEXT,                    -- 该大题的答题要求，如"对的打√，错的打×"
    knowledge_id    TEXT NOT NULL,
    question_id     TEXT NOT NULL,
    score           INTEGER NOT NULL,
    rendered_stem   TEXT NOT NULL,               -- 渲染后题干（占位符已替换）
    rendered_solution TEXT,
    figure_svg      TEXT,
    choices         TEXT,                        -- JSON 数组（选择题）
    answer          TEXT NOT NULL,               -- 由 answer_expr 算出的最终答案
    answer_unit     TEXT
);
CREATE INDEX IF NOT EXISTS idx_item_paper ON paper_items(paper_id);

-- -----------------------------------------------------------------------------
-- 作答：一次尝试 = 一套卷的一次完整作答
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS attempts (
    id              TEXT PRIMARY KEY,            -- UUID
    paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    student_name    TEXT NOT NULL DEFAULT '练习者',
    started_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    submitted_at    TEXT,
    remaining_sec   INTEGER,                     -- 交卷时的剩余秒数
    total_score     INTEGER,
    objective_score INTEGER,                     -- 客观题实得
    subjective_score INTEGER,                    -- 主观题实得（暂同客观，按 Step 给分）
    report          TEXT                         -- JSON：分模块得分率、薄弱知识点
);

CREATE TABLE IF NOT EXISTS attempt_answers (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    attempt_id      TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    item_id         INTEGER NOT NULL REFERENCES paper_items(id) ON DELETE CASCADE,
    student_answer  TEXT,
    scratch         TEXT,                        -- 解题过程，不判分，留给自己看思路
    is_correct      INTEGER NOT NULL DEFAULT 0,
    got_score       INTEGER NOT NULL DEFAULT 0
);

-- 同一份作答里，同一道题只允许有一条记录：
-- 定时保存会反复 UPSERT 这行，缺了这个唯一约束，ON CONFLICT(attempt_id, item_id)
-- 会报 "does not match any PRIMARY KEY or UNIQUE constraint"。
CREATE UNIQUE INDEX IF NOT EXISTS ux_attempt_answers ON attempt_answers(attempt_id, item_id);
CREATE INDEX IF NOT EXISTS idx_ans_attempt ON attempt_answers(attempt_id);

-- -----------------------------------------------------------------------------
-- 错题本：按知识点聚合，用于错题回溯到断链根
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wrong_book (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_id        TEXT NOT NULL REFERENCES knowledge_nodes(id) ON DELETE CASCADE,
    attempt_id          TEXT NOT NULL REFERENCES attempts(id) ON DELETE CASCADE,
    item_id             INTEGER NOT NULL,
    paper_id            TEXT NOT NULL,
    wrong_count         INTEGER NOT NULL DEFAULT 1,
    last_wrong_at       TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_wrong_kn ON wrong_book(knowledge_id);

-- -----------------------------------------------------------------------------
-- 同步水位
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sync_state (
    target      TEXT PRIMARY KEY,                -- 'questions' / 'knowledge'
    last_synced TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    note        TEXT
);
