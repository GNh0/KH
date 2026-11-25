-- =============================================
-- AUTHOR:      사용자
-- CREATE DATE: 2026.11.19
-- DESCRIPTION: 외주발주 처리
-- =============================================
CREATE PROCEDURE [dbo].[sp_XM100500_SAVE]
      @WORKTYPE   VARCHAR(20)
    , @ORGDIV     VARCHAR(2)
    , @USERID     VARCHAR(50)
    , @USERIP     VARCHAR(100)
    , @XML_XX100T VARCHAR(MAX)
    , @XML_XX110T VARCHAR(MAX)
    , @OUTPUT     VARCHAR(20) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    EXEC SP_LOG_XML @@PROCID, @WORKTYPE, @USERID, @XML_XX100T, @XML_XX110T;

    DECLARE @DOC_ID         INT
          , @STARTTRANCOUNT INT = @@TRANCOUNT
          , @PURNUM         VARCHAR(20)
          , @PURDT          VARCHAR(8)
          , @NEWSEQ         INT
          , @OUTSEQ         INT
          , @OUTSEQ2        INT
          , @PURSEQ2        NUMERIC(5, 0)
          , @PREVITEMCD     VARCHAR(100)
          , @PREVPROCCD     VARCHAR(5)
          , @LOTNUM         VARCHAR(50)
          , @QTY            NUMERIC(18, 4)
          , @INRECDT        VARCHAR(50)
          , @INSEQ1         INT
          , @INSEQ2         INT
          , @STOCKQTY       NUMERIC(18, 4)
          , @OUTQTY         NUMERIC(18, 4)
          , @ISSUEQTY       NUMERIC(18, 4)

    DECLARE @TMPXX100T TABLE
    (
          PURNUM VARCHAR(20)      , PURDT     VARCHAR(8)    , CUSTCD    VARCHAR(20)
        , CUSTNM VARCHAR(200)     , PAYMETH1  VARCHAR(3)    , PRCTERMS  VARCHAR(3)
        , AMTUNIT VARCHAR(10)     , PURPERSON VARCHAR(10)  , WONCHGRAT NUMERIC(9, 4)
        , REMARK VARCHAR(500)     , ATTDATNUM VARCHAR(20)
    )

    DECLARE @TMPXX110T TABLE
    (
          SEQ INT IDENTITY(1, 1)  , GBN VARCHAR(3)           , PURSEQ2 NUMERIC(5, 0)
        , PURSTS VARCHAR(1)       , ITEMCD VARCHAR(100)      , QTY NUMERIC(18, 4)
        , QTYUNIT VARCHAR(4)      , UNITWGT NUMERIC(18, 4)   , WGTUNIT VARCHAR(2)
        , UNP NUMERIC(18, 4)      , AMT NUMERIC(18, 4)       , WONAMT NUMERIC(11, 0)
        , TAXAMT NUMERIC(18, 4)   , UNPCALMETH VARCHAR(1)    , DLVDT VARCHAR(8)
        , REMARK VARCHAR(200)     , PLNNUM VARCHAR(20)       , PLNSEQ INT
        , PROCCD VARCHAR(5)       , LOTNUM VARCHAR(50)       , PREVITEMCD VARCHAR(100)
        , PREVPROCCD VARCHAR(5)
    )

    DECLARE @TMPPURSEQ2 TABLE
    (
        PURSEQ2 NUMERIC(5, 0) PRIMARY KEY
    )

    BEGIN TRY
        IF ISNULL(@WORKTYPE, '') NOT IN ('NEW', 'EDIT', 'DELETE')
        BEGIN
            RAISERROR('처리구분을 확인해주세요.', 16, 1);
            RETURN;
        END

        EXEC SP_XML_PREPAREDOCUMENT @DOC_ID OUTPUT, @XML_XX100T

        INSERT INTO @TMPXX100T (PURNUM, PURDT, CUSTCD, CUSTNM, PAYMETH1, PRCTERMS, AMTUNIT, PURPERSON, WONCHGRAT, REMARK, ATTDATNUM)
        SELECT A.PURNUM, A.PURDT, A.CUSTCD, A.CUSTNM, A.PAYMETH1, A.PRCTERMS, A.AMTUNIT, A.PURPERSON, A.WONCHGRAT, A.REMARK, A.ATTDATNUM
        FROM OPENXML (@DOC_ID, '/ROOT/XX100T', 1)
        WITH
        (
              PURNUM VARCHAR(20)      , PURDT     VARCHAR(8)    , CUSTCD    VARCHAR(20)
            , CUSTNM VARCHAR(200)     , PAYMETH1  VARCHAR(3)    , PRCTERMS  VARCHAR(3)
            , AMTUNIT VARCHAR(10)     , PURPERSON VARCHAR(10)  , WONCHGRAT NUMERIC(9, 4)
            , REMARK VARCHAR(500)     , ATTDATNUM VARCHAR(20)
        ) A

        EXEC SP_XML_REMOVEDOCUMENT @DOC_ID
        SET @DOC_ID = NULL

        EXEC SP_XML_PREPAREDOCUMENT @DOC_ID OUTPUT, @XML_XX110T

        INSERT INTO @TMPXX110T
        (
               GBN          , PURSEQ2   , PURSTS
             , ITEMCD       , QTY       , QTYUNIT
             , UNITWGT      , WGTUNIT   , UNP
             , AMT          , WONAMT    , TAXAMT
             , UNPCALMETH   , DLVDT     , REMARK
             , PLNNUM       , PLNSEQ    , PROCCD
             , LOTNUM
        )
        SELECT A.GBN        , A.PURSEQ2 , A.PURSTS
             , A.ITEMCD     , A.QTY     , A.QTYUNIT
             , A.UNITWGT    , A.WGTUNIT , A.UNP
             , A.AMT        , A.WONAMT  , A.TAXAMT
             , A.UNPCALMETH , A.DLVDT   , A.REMARK
             , A.PLNNUM     , A.PLNSEQ  , A.PROCCD
             , A.LOTNUM
        FROM OPENXML (@DOC_ID, '/ROOT/XX110T', 1)
        WITH
        (
              GBN VARCHAR(3)           , PURSEQ2 NUMERIC(5, 0)  , PURSTS VARCHAR(1)
            , ITEMCD VARCHAR(100)      , QTY NUMERIC(18, 4)     , QTYUNIT VARCHAR(4)
            , UNITWGT NUMERIC(18, 4)   , WGTUNIT VARCHAR(2)     , UNP NUMERIC(18, 4)
            , AMT NUMERIC(18, 4)       , WONAMT NUMERIC(11, 0)  , TAXAMT NUMERIC(18, 4)
            , UNPCALMETH VARCHAR(1)    , DLVDT VARCHAR(8)      , REMARK VARCHAR(200)
            , PLNNUM VARCHAR(20)       , PLNSEQ INT            , PROCCD VARCHAR(5)
            , LOTNUM VARCHAR(50)
        ) A

        EXEC SP_XML_REMOVEDOCUMENT @DOC_ID
        SET @DOC_ID = NULL

        SELECT @PURNUM = A.PURNUM
             , @PURDT = A.PURDT
        FROM @TMPXX100T A

        IF @STARTTRANCOUNT = 0
        BEGIN
            BEGIN TRANSACTION
        END

        IF EXISTS (
                   SELECT 1
                   FROM @TMPXX100T A
                           LEFT OUTER JOIN XX100T B
                                        ON B.ORGDIV = @ORGDIV
                                        AND A.PURNUM = B.PURNUM
                                        AND B.PURDIV = '2'
                   WHERE @WORKTYPE IN ('EDIT', 'DELETE')
                     AND B.PURNUM IS NULL
                  )
        BEGIN
            RAISERROR('외주발주 자료를 확인해주세요.', 16, 1);
            RETURN;
        END

        IF EXISTS (
                   SELECT 1
                   FROM @TMPXX100T A
                           INNER JOIN XM210T B
                                   ON B.ORGDIV = @ORGDIV
                                   AND A.PURNUM = B.PURNUM
                   WHERE @WORKTYPE IN ('EDIT', 'DELETE')
                  )
        BEGIN
            RAISERROR('외주입고가 등록된 발주는 수정하거나 삭제할 수 없습니다.', 16, 1);
            RETURN;
        END

        UPDATE A
        SET A.PREVITEMCD = B.PREVITEMCD
          , A.PREVPROCCD = B.PREVPROCCD
        FROM @TMPXX110T A
                INNER JOIN (
                            SELECT T.ORDNUM AS PLNNUM
                                 , T.ORGDIV
                                 , T.ORDSEQ AS PLNSEQ
                                 , T.SDATE AS PLANDT
                                 , T.PROCCD
                                 , T.ITEMCD
                                 , T2.PREVITEMCD
                                 , T2.PREVPROCCD
                            FROM XP110T T
                                    INNER JOIN XS110T T1
                                            ON T.ORGDIV = T1.ORGDIV
                                            AND T.SAORDNUM = T1.ORDNUM
                                            AND T.SAORDSEQ = T1.ORDSEQ
                                    INNER JOIN (
                                                SELECT T.PRNTITEMCD, T.CHLDITEMCD, T.PROCCD
                                                     , LAG(T.CHLDITEMCD) OVER (PARTITION BY T.PRNTITEMCD ORDER BY T.SORT, T.PROCCD, T.CHLDITEMCD) AS PREVITEMCD
                                                     , LAG(T.PROCCD) OVER (PARTITION BY T.PRNTITEMCD ORDER BY T.SORT, T.PROCCD, T.CHLDITEMCD) AS PREVPROCCD
                                                FROM MS031T T
                                                WHERE T.USEYN = 'Y' OR T.USEYN IS NULL
                                               ) T2
                                               ON T1.ITEMCD = T2.PRNTITEMCD
                                               AND T.ITEMCD = T2.CHLDITEMCD
                                               AND T.PROCCD = T2.PROCCD
                                    INNER JOIN MS011T T3
                                            ON T3.MAINCD = 'BA030'
                                            AND T.PROCCD = T3.SUBCD
                                            AND T3.USEYN = 'Y'
                                            AND T3.CHRREF1 = 'Y'
                            WHERE T.ORGDIV = @ORGDIV
                           ) B
                           ON A.PLNNUM = B.PLNNUM
                           AND A.PLNSEQ = B.PLNSEQ
                           AND A.PROCCD = B.PROCCD
                           AND A.ITEMCD = B.ITEMCD
                LEFT OUTER JOIN (
                                 SELECT DISTINCT T.ORGDIV, T.ITEMCD
                                 FROM XP110T T
                                         LEFT OUTER JOIN (
                                                          SELECT T.ORGDIV, T.ORDNUM, T.ORDSEQ, T.PROCCD
                                                               , SUM(T1.QTY) AS QTY
                                                          FROM XP210T T
                                                                  CROSS APPLY (
                                                                               SELECT T.PRODQTY AS QTY

                                                                               UNION ALL

                                                                               SELECT T1.BADQTY
                                                                               FROM XP212T T1
                                                                               WHERE T1.ORGDIV = T.ORGDIV
                                                                                 AND T1.PRODNUM = T.RECDT + '-' + CONVERT(VARCHAR(10), T.SEQ1)
                                                                                 AND T1.PRODSEQ = T.SEQ2
                                                                              ) T1
                                                          WHERE T.ORGDIV = @ORGDIV
                                                          GROUP BY T.ORGDIV, T.ORDNUM, T.ORDSEQ, T.PROCCD
                                                         ) T1
                                                         ON T.ORGDIV = T1.ORGDIV
                                                         AND T.ORDNUM = T1.ORDNUM
                                                         AND T.ORDSEQ = T1.ORDSEQ
                                                         AND T.PROCCD = T1.PROCCD
                                 WHERE T.ORGDIV = @ORGDIV
                                   AND T.PROCCD = '00'
                                   AND (T.FINYN = 'Y' OR ISNULL(T1.QTY, 0) >= T.QTY)
                                ) B1
                                ON B.ORGDIV = B1.ORGDIV
                                AND B.PREVPROCCD = '00'
                                AND B.PREVITEMCD = B1.ITEMCD
                LEFT OUTER JOIN (
                                 SELECT DISTINCT T.ORGDIV, T.PROCCD, T.ITEMCD, T.ORDNUM, T.ORDSEQ
                                 FROM XP110T T
                                         LEFT OUTER JOIN (
                                                          SELECT T.ORGDIV, T.ORDNUM, T.ORDSEQ, T.PROCCD
                                                               , SUM(T1.QTY) AS QTY
                                                          FROM XP210T T
                                                                  CROSS APPLY (
                                                                               SELECT T.PRODQTY AS QTY

                                                                               UNION ALL

                                                                               SELECT T1.BADQTY
                                                                               FROM XP212T T1
                                                                               WHERE T1.ORGDIV = T.ORGDIV
                                                                                 AND T1.PRODNUM = T.RECDT + '-' + CONVERT(VARCHAR(10), T.SEQ1)
                                                                                 AND T1.PRODSEQ = T.SEQ2
                                                                              ) T1
                                                          WHERE T.ORGDIV = @ORGDIV
                                                          GROUP BY T.ORGDIV, T.ORDNUM, T.ORDSEQ, T.PROCCD
                                                         ) T1
                                                         ON T.ORGDIV = T1.ORGDIV
                                                         AND T.ORDNUM = T1.ORDNUM
                                                         AND T.ORDSEQ = T1.ORDSEQ
                                                         AND T.PROCCD = T1.PROCCD
                                 WHERE T.ORGDIV = @ORGDIV
                                   AND T.PROCCD <> '00'
                                   AND (T.FINYN = 'Y' OR ISNULL(T1.QTY, 0) >= T.QTY)
                                ) B2
                                ON B.ORGDIV = B2.ORGDIV
                                AND B.PREVPROCCD = B2.PROCCD
                                AND B.PREVITEMCD = B2.ITEMCD
                                AND B.PLNNUM = B2.ORDNUM
                                AND B.PLNSEQ = B2.ORDSEQ
                LEFT OUTER JOIN XX110T A1
                             ON A1.ORGDIV = @ORGDIV
                             AND A1.PURNUM = @PURNUM
                             AND A.PURSEQ2 = A1.PURSEQ2
                             AND A.PLNNUM = A1.PLNNUM
                             AND A.PLNSEQ = A1.PLNSEQ
                             AND A.PROCCD = A1.PROCCD
                             AND A.ITEMCD = A1.ITEMCD
                             AND A.LOTNUM = A1.LOTNUM
        WHERE @WORKTYPE IN ('NEW', 'EDIT')
          AND (A.GBN = 'NEW' OR (A.GBN = 'MOD' AND A1.PURSEQ2 IS NOT NULL))
          AND (B1.ITEMCD IS NOT NULL OR B2.ITEMCD IS NOT NULL)

        IF EXISTS (
                   SELECT 1
                   FROM @TMPXX110T A
                   WHERE @WORKTYPE IN ('NEW', 'EDIT')
                     AND A.GBN IN ('NEW', 'MOD')
                     AND A.PREVITEMCD IS NULL
                  )
        BEGIN
            RAISERROR('이전공정이 완료된 외주 작업지시를 선택해주세요.', 16, 1);
            RETURN;
        END

        IF @WORKTYPE = 'NEW'
        BEGIN
            EXEC SP_NEW_KEY @ORGDIV, 'XX100T', @PURDT, @NEWSEQ OUTPUT
            SET @PURNUM = @PURDT + '-' + CONVERT(VARCHAR(10), @NEWSEQ)

            INSERT INTO XX100T
            (
                   ORGDIV      , PURNUM      , PURDT       , CUSTCD
                 , CUSTNM      , PAYMETH1    , PRCTERMS    , AMTUNIT
                 , PURPERSON   , WONCHGRAT   , TAXDIV      , PURSTS
                 , PURDIV      , REMARK      , ATTDATNUM   , REGDT
                 , REGEMPNO    , REGIP
            )
            SELECT @ORGDIV     , @PURNUM     , A.PURDT     , A.CUSTCD
                 , A.CUSTNM    , A.PAYMETH1  , A.PRCTERMS  , A.AMTUNIT
                 , A.PURPERSON , A.WONCHGRAT , 'A'         , '2'
                 , '2'         , A.REMARK    , A.ATTDATNUM , GETDATE()
                 , @USERID     , @USERIP
            FROM @TMPXX100T A

            INSERT INTO XX110T
            (
                   ORGDIV            , PURNUM                                                        , PURSEQ2                                                               , PURDIV
                 , PURSTS            , PURDT                                                         , DLVDT                                                                 , CUSTCD
                 , ITEMCD            , ITEMNM                                                        , ITEMACNT                                                              , BNATUR
                 , QTY               , QTYUNIT                                                       , UNP                                                                   , AMT
                 , WONAMT            , TAXAMT                                                        , AMTUNIT                                                               , WONCHGRAT
                 , TAXDIV            , UNPCALMETH                                                    , PLNNUM                                                                , PLNSEQ
                 , PROCCD            , LOTNUM                                                        , REMARK                                                                , REGDT
                 , REGEMPNO          , REGIP                                                         , UNITWGT                                                               , WGTUNIT
                 , TOTWGT            , UNITKG                                                        , TOTWGTKG
            )
            OUTPUT INSERTED.PURSEQ2 INTO @TMPPURSEQ2 (PURSEQ2)
            SELECT @ORGDIV           , @PURNUM                                                       , ISNULL(D.PURSEQ2, 0) + ROW_NUMBER() OVER (ORDER BY A.SEQ)             , '2'
                 , A.PURSTS          , B.PURDT                                                       , A.DLVDT                                                               , B.CUSTCD
                 , A.ITEMCD          , C.ITEMNM                                                      , C.ITEMACNT                                                            , C.BNATUR
                 , A.QTY             , A.QTYUNIT                                                     , A.UNP                                                                 , A.AMT
                 , A.WONAMT          , A.TAXAMT                                                      , B.AMTUNIT                                                             , B.WONCHGRAT
                 , 'A'               , A.UNPCALMETH                                                  , A.PLNNUM                                                              , A.PLNSEQ
                 , A.PROCCD          , A.LOTNUM                                                      , A.REMARK                                                              , GETDATE()
                 , @USERID           , @USERIP                                                       , A.UNITWGT                                                             , A.WGTUNIT
                 , A.QTY * A.UNITWGT , A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END) , A.QTY * A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
            FROM @TMPXX110T A
                    CROSS JOIN @TMPXX100T B
                    INNER JOIN MS030T C
                            ON A.ITEMCD = C.ITEMCD
                    LEFT OUTER JOIN (
                                     SELECT T.ORGDIV
                                          , T.PURNUM
                                          , MAX(T.PURSEQ2) AS PURSEQ2
                                     FROM XX110T T
                                     WHERE T.ORGDIV = @ORGDIV
                                       AND T.PURNUM = @PURNUM
                                     GROUP BY T.ORGDIV, T.PURNUM
                                    ) D
                                    ON D.ORGDIV = @ORGDIV
                                    AND D.PURNUM = @PURNUM
            WHERE A.GBN = 'NEW'

            IF NOT EXISTS (
                           SELECT 1
                           FROM XX110T A
                           WHERE A.ORGDIV = @ORGDIV
                             AND A.PURNUM = @PURNUM
                          )
            BEGIN
                RAISERROR('발주 상세를 확인해주세요.', 16, 1);
                RETURN;
            END

            IF EXISTS (
                       SELECT 1
                       FROM @TMPPURSEQ2
                      )
            BEGIN
                EXEC SP_NEW_KEY @ORGDIV, 'SY100T', @PURDT, @OUTSEQ OUTPUT
                SET @OUTSEQ2 = 0

                WHILE EXISTS (
                              SELECT 1
                              FROM @TMPPURSEQ2
                             )
                BEGIN
                    SELECT TOP 1 @PURSEQ2 = A.PURSEQ2
                    FROM @TMPPURSEQ2 A
                    ORDER BY A.PURSEQ2

                    SET @QTY = NULL
                    SELECT @QTY = A.QTY
                         , @LOTNUM = A.LOTNUM
                         , @PREVITEMCD = B.PREVITEMCD
                         , @PREVPROCCD = B.PREVPROCCD
                    FROM XX110T A
                            INNER JOIN (
                                        SELECT DISTINCT T.PLNNUM, T.PLNSEQ, T.PROCCD, T.ITEMCD, T.LOTNUM
                                             , T.PREVITEMCD, T.PREVPROCCD
                                        FROM @TMPXX110T T
                                        WHERE T.GBN IN ('NEW', 'MOD')
                                       ) B
                                       ON A.PLNNUM = B.PLNNUM
                                       AND A.PLNSEQ = B.PLNSEQ
                                       AND A.PROCCD = B.PROCCD
                                       AND A.ITEMCD = B.ITEMCD
                                       AND A.LOTNUM = B.LOTNUM
                    WHERE A.ORGDIV = @ORGDIV
                      AND A.PURNUM = @PURNUM
                      AND A.PURSEQ2 = @PURSEQ2

                    IF @QTY IS NULL OR @QTY <= 0
                    BEGIN
                        RAISERROR('발주 상세의 수량을 확인해주세요.', 16, 1);
                        RETURN;
                    END

                    WHILE @QTY > 0
                    BEGIN
                        SET @INRECDT = NULL
                        SELECT TOP 1 @INRECDT = A.RECDT
                             , @INSEQ1 = A.SEQ1
                             , @INSEQ2 = A.SEQ2
                             , @STOCKQTY = A.QTY
                             , @OUTQTY = ISNULL(B.QTY, 0)
                        FROM XM210T A
                                LEFT OUTER JOIN (
                                                 SELECT T.INRECDT, T.INSEQ1, T.INSEQ2
                                                      , SUM(T.QTY) AS QTY
                                                 FROM XS210T T
                                                 WHERE T.ORGDIV = @ORGDIV
                                                 GROUP BY T.INRECDT, T.INSEQ1, T.INSEQ2
                                                ) B
                                                ON A.RECDT = B.INRECDT
                                                AND A.SEQ1 = B.INSEQ1
                                                AND A.SEQ2 = B.INSEQ2
                        WHERE A.ORGDIV = @ORGDIV
                          AND A.ITEMCD = @PREVITEMCD
                          AND A.PROCCD = @PREVPROCCD
                          AND A.ORGLOTNUM = @LOTNUM
                          AND ISNULL(A.QTYUNIT, '') IN ('', 'EA')
                          AND A.QTY > ISNULL(B.QTY, 0)
                        ORDER BY A.INDT, A.RECDT, A.SEQ1, A.SEQ2

                        IF @INRECDT IS NULL
                        BEGIN
                            RAISERROR('외주발주 수량이 이전공정의 단조 LOT 재고 잔량을 초과합니다.', 16, 1);
                            RETURN;
                        END

                        SET @STOCKQTY = @STOCKQTY - @OUTQTY
                        SET @ISSUEQTY = (CASE WHEN @QTY > @STOCKQTY THEN @STOCKQTY ELSE @QTY END)
                        SET @OUTSEQ2 = @OUTSEQ2 + 1

                        INSERT INTO XS210T
                        (
                               ORGDIV     , RECDT     , SEQ1        , SEQ2
                             , LOCATION   , CUSTCD    , OUTDT       , OUTYRMM
                             , OUTKIND    , OUTTYPE   , ITEMCD      , ITEMNM
                             , ITEMACNT   , BNATUR    , INSIZ       , QTY
                             , QTYUNIT    , UNITWGT   , UNITKG      , TOTWGT
                             , WGTUNIT    , LOTNUM    , ITEMGRADE   , MNGITEM1
                             , OUTDPTCHK  , INRECDT   , INSEQ1      , INSEQ2
                             , PLNNUM     , PLNSEQ    , PURNUM      , PURSEQ2
                             , PROCPGMID  , REGDT     , REGEMPNO    , REGIP
                        )
                        SELECT @ORGDIV    , @PURDT    , @OUTSEQ     , @OUTSEQ2
                             , A.LOCATION , C.CUSTCD  , @PURDT      , LEFT(@PURDT, 6)
                             , 'F'        , 'A'       , A.ITEMCD    , A.ITEMNM
                             , A.ITEMACNT , A.BNATUR  , A.INSIZ     , @ISSUEQTY
                             , 'EA'       , A.UNITWGT , A.UNITKG    , @ISSUEQTY * ISNULL(A.TOTWGT / NULLIF(A.QTY, 0), 0)
                             , A.WGTUNIT  , B.LOTNUM  , A.ITEMGRADE , A.MNGITEM1
                             , 'B'        , A.RECDT   , A.SEQ1      , A.SEQ2
                             , B.PLNNUM   , B.PLNSEQ  , @PURNUM     , B.PURSEQ2
                             , 'XM100500' , GETDATE() , @USERID     , @USERIP
                        FROM XM210T A
                                INNER JOIN XX110T B
                                        ON B.ORGDIV = @ORGDIV
                                        AND B.PURNUM = @PURNUM
                                        AND B.PURSEQ2 = @PURSEQ2
                                CROSS JOIN @TMPXX100T C
                        WHERE A.ORGDIV = @ORGDIV
                          AND A.RECDT = @INRECDT
                          AND A.SEQ1 = @INSEQ1
                          AND A.SEQ2 = @INSEQ2

                        SET @QTY = @QTY - @ISSUEQTY
                    END

                    DELETE A
                    FROM @TMPPURSEQ2 A
                    WHERE A.PURSEQ2 = @PURSEQ2
                END

                IF EXISTS (
                           SELECT 1
                           FROM XS210T A
                                   INNER JOIN XM210T B
                                           ON A.ORGDIV = B.ORGDIV
                                           AND A.INRECDT = B.RECDT
                                           AND A.INSEQ1 = B.SEQ1
                                           AND A.INSEQ2 = B.SEQ2
                                   INNER JOIN (
                                               SELECT T.INRECDT, T.INSEQ1, T.INSEQ2
                                                    , SUM(T.QTY) AS QTY
                                               FROM XS210T T
                                               WHERE T.ORGDIV = @ORGDIV
                                               GROUP BY T.INRECDT, T.INSEQ1, T.INSEQ2
                                              ) C
                                              ON A.INRECDT = C.INRECDT
                                              AND A.INSEQ1 = C.INSEQ1
                                              AND A.INSEQ2 = C.INSEQ2
                           WHERE A.ORGDIV = @ORGDIV
                             AND A.RECDT = @PURDT
                             AND A.SEQ1 = @OUTSEQ
                             AND A.PROCPGMID = 'XM100500'
                             AND C.QTY > B.QTY
                          )
                BEGIN
                    RAISERROR('외주발주 수량이 이전공정의 단조 LOT 재고 잔량을 초과합니다.', 16, 1);
                    RETURN;
                END
            END
        END
        ELSE IF @WORKTYPE = 'EDIT'
        BEGIN
            UPDATE A
            SET A.PURDT     = B.PURDT
              , A.CUSTCD    = B.CUSTCD
              , A.CUSTNM    = B.CUSTNM
              , A.PAYMETH1  = B.PAYMETH1
              , A.PRCTERMS  = B.PRCTERMS
              , A.AMTUNIT   = B.AMTUNIT
              , A.PURPERSON = B.PURPERSON
              , A.WONCHGRAT = B.WONCHGRAT
              , A.REMARK    = B.REMARK
              , A.ATTDATNUM = B.ATTDATNUM
              , A.MODDT     = GETDATE()
              , A.MODEMPNO  = @USERID
              , A.MODIP     = @USERIP
            FROM XX100T A
                    INNER JOIN @TMPXX100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV

            DELETE A
            FROM XS210T A
                    INNER JOIN @TMPXX110T B
                            ON A.PURSEQ2 = B.PURSEQ2
                            AND B.GBN IN ('MOD', 'DEL')
            WHERE A.ORGDIV = @ORGDIV
              AND A.PURNUM = @PURNUM
              AND A.PROCPGMID = 'XM100500'

            DELETE A
            FROM XX110T A
                    INNER JOIN @TMPXX110T B
                            ON A.PURSEQ2 = B.PURSEQ2
            WHERE A.ORGDIV = @ORGDIV
              AND A.PURNUM = @PURNUM
              AND B.GBN = 'DEL'

            UPDATE A
            SET A.PURDT     = B.PURDT
              , A.CUSTCD    = B.CUSTCD
              , A.AMTUNIT   = B.AMTUNIT
              , A.WONCHGRAT = B.WONCHGRAT
            FROM XX110T A
                    INNER JOIN @TMPXX100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV

            UPDATE A
            SET A.OUTDT    = B.PURDT
              , A.OUTYRMM  = LEFT(B.PURDT, 6)
              , A.CUSTCD   = B.CUSTCD
              , A.MODDT    = GETDATE()
              , A.MODEMPNO = @USERID
              , A.MODIP    = @USERIP
            FROM XS210T A
                    INNER JOIN @TMPXX100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV
              AND A.PROCPGMID = 'XM100500'

            UPDATE A
            SET A.PURSTS      = B.PURSTS
              , A.QTY         = B.QTY
              , A.UNITWGT     = B.UNITWGT
              , A.WGTUNIT     = B.WGTUNIT
              , A.TOTWGT      = B.QTY * B.UNITWGT
              , A.UNITKG      = B.UNITWGT * (CASE WHEN B.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
              , A.TOTWGTKG    = B.QTY * B.UNITWGT * (CASE WHEN B.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
              , A.UNP         = B.UNP
              , A.AMT         = B.AMT
              , A.WONAMT      = B.WONAMT
              , A.TAXAMT      = B.TAXAMT
              , A.UNPCALMETH  = B.UNPCALMETH
              , A.DLVDT       = B.DLVDT
              , A.REMARK      = B.REMARK
              , A.MODDT       = GETDATE()
              , A.MODEMPNO    = @USERID
              , A.MODIP       = @USERIP
            OUTPUT INSERTED.PURSEQ2 INTO @TMPPURSEQ2 (PURSEQ2)
            FROM XX110T A
                    INNER JOIN @TMPXX110T B
                            ON A.PURSEQ2 = B.PURSEQ2
                            AND A.PLNNUM = B.PLNNUM
                            AND A.PLNSEQ = B.PLNSEQ
                            AND A.PROCCD = B.PROCCD
                            AND A.LOTNUM = B.LOTNUM
                            AND A.ITEMCD = B.ITEMCD
            WHERE A.ORGDIV = @ORGDIV
              AND A.PURNUM = @PURNUM
              AND B.GBN = 'MOD'

            INSERT INTO XX110T
            (
                   ORGDIV            , PURNUM                                                        , PURSEQ2                                                               , PURDIV
                 , PURSTS            , PURDT                                                         , DLVDT                                                                 , CUSTCD
                 , ITEMCD            , ITEMNM                                                        , ITEMACNT                                                              , BNATUR
                 , QTY               , QTYUNIT                                                       , UNP                                                                   , AMT
                 , WONAMT            , TAXAMT                                                        , AMTUNIT                                                               , WONCHGRAT
                 , TAXDIV            , UNPCALMETH                                                    , PLNNUM                                                                , PLNSEQ
                 , PROCCD            , LOTNUM                                                        , REMARK                                                                , REGDT
                 , REGEMPNO          , REGIP                                                         , UNITWGT                                                               , WGTUNIT
                 , TOTWGT            , UNITKG                                                        , TOTWGTKG
            )
            OUTPUT INSERTED.PURSEQ2 INTO @TMPPURSEQ2 (PURSEQ2)
            SELECT @ORGDIV           , @PURNUM                                                       , ISNULL(D.PURSEQ2, 0) + ROW_NUMBER() OVER (ORDER BY A.SEQ)             , '2'
                 , A.PURSTS          , B.PURDT                                                       , A.DLVDT                                                               , B.CUSTCD
                 , A.ITEMCD          , C.ITEMNM                                                      , C.ITEMACNT                                                            , C.BNATUR
                 , A.QTY             , A.QTYUNIT                                                     , A.UNP                                                                 , A.AMT
                 , A.WONAMT          , A.TAXAMT                                                      , B.AMTUNIT                                                             , B.WONCHGRAT
                 , 'A'               , A.UNPCALMETH                                                  , A.PLNNUM                                                              , A.PLNSEQ
                 , A.PROCCD          , A.LOTNUM                                                      , A.REMARK                                                              , GETDATE()
                 , @USERID           , @USERIP                                                       , A.UNITWGT                                                             , A.WGTUNIT
                 , A.QTY * A.UNITWGT , A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END) , A.QTY * A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
            FROM @TMPXX110T A
                    CROSS JOIN @TMPXX100T B
                    INNER JOIN MS030T C
                            ON A.ITEMCD = C.ITEMCD
                    LEFT OUTER JOIN (
                                     SELECT T.ORGDIV
                                          , T.PURNUM
                                          , MAX(T.PURSEQ2) AS PURSEQ2
                                     FROM XX110T T
                                     WHERE T.ORGDIV = @ORGDIV
                                       AND T.PURNUM = @PURNUM
                                     GROUP BY T.ORGDIV, T.PURNUM
                                    ) D
                                    ON D.ORGDIV = @ORGDIV
                                    AND D.PURNUM = @PURNUM
            WHERE A.GBN = 'NEW'

            IF NOT EXISTS (
                           SELECT 1
                           FROM XX110T A
                           WHERE A.ORGDIV = @ORGDIV
                             AND A.PURNUM = @PURNUM
                          )
            BEGIN
                RAISERROR('발주 상세를 확인해주세요.', 16, 1);
                RETURN;
            END

            IF EXISTS (
                       SELECT 1
                       FROM @TMPPURSEQ2
                      )
            BEGIN
                EXEC SP_NEW_KEY @ORGDIV, 'SY100T', @PURDT, @OUTSEQ OUTPUT
                SET @OUTSEQ2 = 0

                WHILE EXISTS (
                              SELECT 1
                              FROM @TMPPURSEQ2
                             )
                BEGIN
                    SELECT TOP 1 @PURSEQ2 = A.PURSEQ2
                    FROM @TMPPURSEQ2 A
                    ORDER BY A.PURSEQ2

                    SET @QTY = NULL
                    SELECT @QTY = A.QTY
                         , @LOTNUM = A.LOTNUM
                         , @PREVITEMCD = B.PREVITEMCD
                         , @PREVPROCCD = B.PREVPROCCD
                    FROM XX110T A
                            INNER JOIN (
                                        SELECT DISTINCT T.PLNNUM, T.PLNSEQ, T.PROCCD, T.ITEMCD, T.LOTNUM
                                             , T.PREVITEMCD, T.PREVPROCCD
                                        FROM @TMPXX110T T
                                        WHERE T.GBN IN ('NEW', 'MOD')
                                       ) B
                                       ON A.PLNNUM = B.PLNNUM
                                       AND A.PLNSEQ = B.PLNSEQ
                                       AND A.PROCCD = B.PROCCD
                                       AND A.ITEMCD = B.ITEMCD
                                       AND A.LOTNUM = B.LOTNUM
                    WHERE A.ORGDIV = @ORGDIV
                      AND A.PURNUM = @PURNUM
                      AND A.PURSEQ2 = @PURSEQ2

                    IF @QTY IS NULL OR @QTY <= 0
                    BEGIN
                        RAISERROR('발주 상세의 수량을 확인해주세요.', 16, 1);
                        RETURN;
                    END

                    WHILE @QTY > 0
                    BEGIN
                        SET @INRECDT = NULL
                        SELECT TOP 1 @INRECDT = A.RECDT
                             , @INSEQ1 = A.SEQ1
                             , @INSEQ2 = A.SEQ2
                             , @STOCKQTY = A.QTY
                             , @OUTQTY = ISNULL(B.QTY, 0)
                        FROM XM210T A
                                LEFT OUTER JOIN (
                                                 SELECT T.INRECDT, T.INSEQ1, T.INSEQ2
                                                      , SUM(T.QTY) AS QTY
                                                 FROM XS210T T
                                                 WHERE T.ORGDIV = @ORGDIV
                                                 GROUP BY T.INRECDT, T.INSEQ1, T.INSEQ2
                                                ) B
                                                ON A.RECDT = B.INRECDT
                                                AND A.SEQ1 = B.INSEQ1
                                                AND A.SEQ2 = B.INSEQ2
                        WHERE A.ORGDIV = @ORGDIV
                          AND A.ITEMCD = @PREVITEMCD
                          AND A.PROCCD = @PREVPROCCD
                          AND A.ORGLOTNUM = @LOTNUM
                          AND ISNULL(A.QTYUNIT, '') IN ('', 'EA')
                          AND A.QTY > ISNULL(B.QTY, 0)
                        ORDER BY A.INDT, A.RECDT, A.SEQ1, A.SEQ2

                        IF @INRECDT IS NULL
                        BEGIN
                            RAISERROR('외주발주 수량이 이전공정의 단조 LOT 재고 잔량을 초과합니다.', 16, 1);
                            RETURN;
                        END

                        SET @STOCKQTY = @STOCKQTY - @OUTQTY
                        SET @ISSUEQTY = (CASE WHEN @QTY > @STOCKQTY THEN @STOCKQTY ELSE @QTY END)
                        SET @OUTSEQ2 = @OUTSEQ2 + 1

                        INSERT INTO XS210T
                        (
                               ORGDIV     , RECDT     , SEQ1        , SEQ2
                             , LOCATION   , CUSTCD    , OUTDT       , OUTYRMM
                             , OUTKIND    , OUTTYPE   , ITEMCD      , ITEMNM
                             , ITEMACNT   , BNATUR    , INSIZ       , QTY
                             , QTYUNIT    , UNITWGT   , UNITKG      , TOTWGT
                             , WGTUNIT    , LOTNUM    , ITEMGRADE   , MNGITEM1
                             , OUTDPTCHK  , INRECDT   , INSEQ1      , INSEQ2
                             , PLNNUM     , PLNSEQ    , PURNUM      , PURSEQ2
                             , PROCPGMID  , REGDT     , REGEMPNO    , REGIP
                        )
                        SELECT @ORGDIV    , @PURDT    , @OUTSEQ     , @OUTSEQ2
                             , A.LOCATION , C.CUSTCD  , @PURDT      , LEFT(@PURDT, 6)
                             , 'F'        , 'A'       , A.ITEMCD    , A.ITEMNM
                             , A.ITEMACNT , A.BNATUR  , A.INSIZ     , @ISSUEQTY
                             , 'EA'       , A.UNITWGT , A.UNITKG    , @ISSUEQTY * ISNULL(A.TOTWGT / NULLIF(A.QTY, 0), 0)
                             , A.WGTUNIT  , B.LOTNUM  , A.ITEMGRADE , A.MNGITEM1
                             , 'B'        , A.RECDT   , A.SEQ1      , A.SEQ2
                             , B.PLNNUM   , B.PLNSEQ  , @PURNUM     , B.PURSEQ2
                             , 'XM100500' , GETDATE() , @USERID     , @USERIP
                        FROM XM210T A
                                INNER JOIN XX110T B
                                        ON B.ORGDIV = @ORGDIV
                                        AND B.PURNUM = @PURNUM
                                        AND B.PURSEQ2 = @PURSEQ2
                                CROSS JOIN @TMPXX100T C
                        WHERE A.ORGDIV = @ORGDIV
                          AND A.RECDT = @INRECDT
                          AND A.SEQ1 = @INSEQ1
                          AND A.SEQ2 = @INSEQ2

                        SET @QTY = @QTY - @ISSUEQTY
                    END

                    DELETE A
                    FROM @TMPPURSEQ2 A
                    WHERE A.PURSEQ2 = @PURSEQ2
                END

                IF EXISTS (
                           SELECT 1
                           FROM XS210T A
                                   INNER JOIN XM210T B
                                           ON A.ORGDIV = B.ORGDIV
                                           AND A.INRECDT = B.RECDT
                                           AND A.INSEQ1 = B.SEQ1
                                           AND A.INSEQ2 = B.SEQ2
                                   INNER JOIN (
                                               SELECT T.INRECDT, T.INSEQ1, T.INSEQ2
                                                    , SUM(T.QTY) AS QTY
                                               FROM XS210T T
                                               WHERE T.ORGDIV = @ORGDIV
                                               GROUP BY T.INRECDT, T.INSEQ1, T.INSEQ2
                                              ) C
                                              ON A.INRECDT = C.INRECDT
                                              AND A.INSEQ1 = C.INSEQ1
                                              AND A.INSEQ2 = C.INSEQ2
                           WHERE A.ORGDIV = @ORGDIV
                             AND A.RECDT = @PURDT
                             AND A.SEQ1 = @OUTSEQ
                             AND A.PROCPGMID = 'XM100500'
                             AND C.QTY > B.QTY
                          )
                BEGIN
                    RAISERROR('외주발주 수량이 이전공정의 단조 LOT 재고 잔량을 초과합니다.', 16, 1);
                    RETURN;
                END
            END
        END
        ELSE IF @WORKTYPE = 'DELETE'
        BEGIN
            DELETE A
            FROM XS210T A
                    INNER JOIN @TMPXX100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV
              AND A.PROCPGMID = 'XM100500'

            DELETE A
            FROM XX110T A
                    INNER JOIN @TMPXX100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV

            DELETE A
            FROM XX100T A
                    INNER JOIN @TMPXX100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV
        END

        SET @OUTPUT = @PURNUM

        IF @STARTTRANCOUNT = 0
        BEGIN
            COMMIT TRANSACTION
        END
    END TRY
    BEGIN CATCH
        IF @DOC_ID IS NOT NULL
        BEGIN
            EXEC SP_XML_REMOVEDOCUMENT @DOC_ID
        END

        IF @STARTTRANCOUNT = 0 AND @@TRANCOUNT > 0
        BEGIN
            ROLLBACK TRANSACTION
        END;

        THROW;
    END CATCH
END
