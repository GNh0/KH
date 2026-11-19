USE [C_KONE120]
GO
/****** Object:  StoredProcedure [dbo].[sp_MA100500_SAVE]    Script Date: 2026-11-19 오후 1:54:06 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
-- =============================================
-- AUTHOR:      근호
-- CREATE DATE: 2026.11.19
-- DESCRIPTION: 외주발주 처리
-- =============================================
ALTER PROCEDURE [dbo].[sp_MA100500_SAVE]
      @WORKTYPE   VARCHAR(20)
    , @ORGDIV     VARCHAR(2)
    , @USERID     VARCHAR(50)
    , @USERIP     VARCHAR(100)
    , @XML_MA100T VARCHAR(MAX)
    , @XML_MA110T VARCHAR(MAX)
    , @OUTPUT     VARCHAR(20) OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    EXEC SP_XML_LOG_SAVE @@PROCID, @WORKTYPE, @USERID, @XML_MA100T, @XML_MA110T;

    DECLARE @DOC_ID         INT
          , @STARTTRANCOUNT INT = @@TRANCOUNT
          , @PURNUM         VARCHAR(20)
          , @PURDT          VARCHAR(8)
          , @NEWSEQ         INT
          , @OUTSEQ         INT

    DECLARE @TMPMA100T TABLE
    (
          PURNUM VARCHAR(20)      , PURDT     VARCHAR(8)    , CUSTCD    VARCHAR(20)
        , CUSTNM VARCHAR(200)     , PAYMETH1  VARCHAR(3)    , PRCTERMS  VARCHAR(3)
        , AMTUNIT VARCHAR(10)     , PURPERSON VARCHAR(10)  , WONCHGRAT NUMERIC(9, 4)
        , REMARK VARCHAR(500)     , ATTDATNUM VARCHAR(20)
    )

    DECLARE @TMPMA110T TABLE
    (
          SEQ INT IDENTITY(1, 1)  , GBN VARCHAR(3)           , PURSEQ2 NUMERIC(5, 0)
        , PURSTS VARCHAR(1)       , ITEMCD VARCHAR(100)      , QTY NUMERIC(18, 4)
        , QTYUNIT VARCHAR(4)      , UNITWGT NUMERIC(18, 4)   , WGTUNIT VARCHAR(2)
        , UNP NUMERIC(18, 4)      , AMT NUMERIC(18, 4)       , WONAMT NUMERIC(11, 0)
        , TAXAMT NUMERIC(18, 4)   , UNPCALMETH VARCHAR(1)    , DLVDT VARCHAR(8)
        , REMARK VARCHAR(200)     , PLNNUM VARCHAR(20)       , PLNSEQ INT
        , PROCCD VARCHAR(5)       , LOTNUM VARCHAR(50)
    )

    BEGIN TRY
        IF ISNULL(@WORKTYPE, '') NOT IN ('NEW', 'EDIT', 'DELETE')
        BEGIN
            RAISERROR('처리구분을 확인해주세요.', 16, 1);
            RETURN;
        END

        EXEC SP_XML_PREPAREDOCUMENT @DOC_ID OUTPUT, @XML_MA100T

        INSERT INTO @TMPMA100T (PURNUM, PURDT, CUSTCD, CUSTNM, PAYMETH1, PRCTERMS, AMTUNIT, PURPERSON, WONCHGRAT, REMARK, ATTDATNUM)
        SELECT A.PURNUM, A.PURDT, A.CUSTCD, A.CUSTNM, A.PAYMETH1, A.PRCTERMS, A.AMTUNIT, A.PURPERSON, A.WONCHGRAT, A.REMARK, A.ATTDATNUM
        FROM OPENXML (@DOC_ID, '/ROOT/MA100T', 1)
        WITH
        (
              PURNUM VARCHAR(20)      , PURDT     VARCHAR(8)    , CUSTCD    VARCHAR(20)
            , CUSTNM VARCHAR(200)     , PAYMETH1  VARCHAR(3)    , PRCTERMS  VARCHAR(3)
            , AMTUNIT VARCHAR(10)     , PURPERSON VARCHAR(10)  , WONCHGRAT NUMERIC(9, 4)
            , REMARK VARCHAR(500)     , ATTDATNUM VARCHAR(20)
        ) A

        EXEC SP_XML_REMOVEDOCUMENT @DOC_ID
        SET @DOC_ID = NULL

        IF @STARTTRANCOUNT = 0
        BEGIN
            BEGIN TRANSACTION
        END

        IF @WORKTYPE IN ('EDIT', 'DELETE')
        BEGIN
            IF NOT EXISTS (
                           SELECT 1
                           FROM @TMPMA100T
                          )
               OR EXISTS (
                          SELECT 1
                          FROM @TMPMA100T A
                                  LEFT OUTER JOIN MA100T B
                                               ON B.ORGDIV = @ORGDIV
                                               AND A.PURNUM = B.PURNUM
                                               AND B.PURDIV = '2'
                          WHERE B.PURNUM IS NULL
                         )
            BEGIN
                RAISERROR('외주발주 자료를 확인해주세요.', 16, 1);
                RETURN;
            END

            IF EXISTS (
                       SELECT 1
                       FROM @TMPMA100T A
                               INNER JOIN MA210T B
                                       ON B.ORGDIV = @ORGDIV
                                       AND A.PURNUM = B.PURNUM
                      )
            BEGIN
                RAISERROR('외주입고가 등록된 발주는 수정하거나 삭제할 수 없습니다.', 16, 1);
                RETURN;
            END
        END

        IF @WORKTYPE = 'DELETE'
        BEGIN
            DELETE A
            FROM SA210T A
                    INNER JOIN @TMPMA100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV
              AND A.PROCPGMID = 'MA100500'

            DELETE A
            FROM MA110T A
                    INNER JOIN @TMPMA100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV

            DELETE A
            FROM MA100T A
                    INNER JOIN @TMPMA100T B
                            ON A.PURNUM = B.PURNUM
            WHERE A.ORGDIV = @ORGDIV
        END
        ELSE IF @WORKTYPE IN ('NEW', 'EDIT')
        BEGIN
            IF (SELECT COUNT(*) FROM @TMPMA100T) <> 1
               OR EXISTS (
                          SELECT 1
                          FROM @TMPMA100T A
                          WHERE ISNULL(A.CUSTCD, '') = ''
                             OR TRY_CONVERT(DATE, NULLIF(A.PURDT, ''), 112) IS NULL
                         )
            BEGIN
                RAISERROR('발주일자와 외주업체를 확인해주세요.', 16, 1);
                RETURN;
            END

            SELECT @PURNUM = A.PURNUM
                 , @PURDT = A.PURDT
            FROM @TMPMA100T A

            EXEC SP_XML_PREPAREDOCUMENT @DOC_ID OUTPUT, @XML_MA110T

            INSERT INTO @TMPMA110T
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
            FROM OPENXML (@DOC_ID, '/ROOT/MA110T', 1)
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

            IF EXISTS (
                       SELECT 1
                       FROM @TMPMA110T A
                       WHERE A.GBN IS NULL
                          OR A.GBN NOT IN ('NEW', 'MOD', 'DEL')
                          OR (@WORKTYPE = 'NEW' AND A.GBN <> 'NEW')
                          OR (A.GBN IN ('NEW', 'MOD')
                              AND (A.QTY IS NULL OR A.QTY <= 0
                                   OR A.QTYUNIT IS NULL OR A.QTYUNIT <> 'EA'
                                   OR A.LOTNUM IS NULL OR A.LOTNUM = ''))
                      )
            BEGIN
                RAISERROR('발주 상세의 계획, 단조 LOT 및 수량을 확인해주세요.', 16, 1);
                RETURN;
            END

            IF EXISTS (
                       SELECT 1
                       FROM @TMPMA110T A
                               LEFT OUTER JOIN (
                                                SELECT T.ORDNUM AS PLNNUM
                                                     , T.ORGDIV
                                                     , T.ORDSEQ AS PLNSEQ
                                                     , T.SDATE AS PLANDT
                                                     , T.PROCCD
                                                     , T.ITEMCD
                                                     , T2.PREVITEMCD
                                                     , T2.PREVPROCCD
                                                FROM PR110T T
                                                        INNER JOIN SA110T T1
                                                                ON T.ORGDIV = T1.ORGDIV
                                                                AND T.SAORDNUM = T1.ORDNUM
                                                                AND T.SAORDSEQ = T1.ORDSEQ
                                                        INNER JOIN (
                                                                    SELECT T.PRNTITEMCD, T.CHLDITEMCD, T.PROCCD
                                                                         , LAG(T.CHLDITEMCD) OVER (PARTITION BY T.PRNTITEMCD ORDER BY T.SORT, T.PROCCD, T.CHLDITEMCD) AS PREVITEMCD
                                                                         , LAG(T.PROCCD) OVER (PARTITION BY T.PRNTITEMCD ORDER BY T.SORT, T.PROCCD, T.CHLDITEMCD) AS PREVPROCCD
                                                                    FROM BA031T T
                                                                    WHERE T.USEYN = 'Y' OR T.USEYN IS NULL
                                                                   ) T2
                                                                   ON T1.ITEMCD = T2.PRNTITEMCD
                                                                   AND T.ITEMCD = T2.CHLDITEMCD
                                                                   AND T.PROCCD = T2.PROCCD
                                                        INNER JOIN BA011T T3
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
                                                SELECT DISTINCT T.ORGDIV, T.PROCCD, T.ITEMCD
                                                     , (CASE WHEN T.PROCCD <> '00' THEN T.ORDNUM END) AS ORDNUM
                                                     , (CASE WHEN T.PROCCD <> '00' THEN T.ORDSEQ END) AS ORDSEQ
                                                FROM PR110T T
                                                        LEFT OUTER JOIN (
                                                                         SELECT T.ORGDIV, T.ORDNUM, T.ORDSEQ, T.PROCCD
                                                                              , SUM(T1.QTY) AS QTY
                                                                         FROM PR210T T
                                                                                 CROSS APPLY (
                                                                                              SELECT T.PRODQTY AS QTY

                                                                                              UNION ALL

                                                                                              SELECT T1.BADQTY
                                                                                              FROM PR212T T1
                                                                                              WHERE T1.ORGDIV = T.ORGDIV
                                                                                                AND T1.PRODNUM = T.RECDT + '-' + CONVERT(VARCHAR(10), T.SEQ1)
                                                                                                AND T1.PRODSEQ = T.SEQ2
                                                                                             ) T1
                                                                         WHERE T.ORGDIV = @ORGDIV
                                                                         GROUP BY T.ORGDIV, T.ORDNUM
                                                                                , T.ORDSEQ, T.PROCCD
                                                                        ) T1
                                                                        ON T.ORGDIV = T1.ORGDIV
                                                                        AND T.ORDNUM = T1.ORDNUM
                                                                        AND T.ORDSEQ = T1.ORDSEQ
                                                                        AND T.PROCCD = T1.PROCCD
                                                WHERE T.ORGDIV = @ORGDIV
                                                  AND (T.FINYN = 'Y' OR ISNULL(T1.QTY, 0) >= T.QTY)
                                               ) B1
                                               ON B.ORGDIV = B1.ORGDIV
                                               AND B.PREVPROCCD = B1.PROCCD
                                               AND B.PREVITEMCD = B1.ITEMCD
                                               AND (B1.PROCCD = '00' OR (B.PLNNUM = B1.ORDNUM AND B.PLNSEQ = B1.ORDSEQ))
                       WHERE A.GBN IN ('NEW', 'MOD')
                         AND B1.ITEMCD IS NULL
                      )
            BEGIN
                RAISERROR('직전공정이 완료된 외주 작업지시를 선택해주세요.', 16, 1);
                RETURN;
            END

            IF EXISTS (
                       SELECT 1
                       FROM @TMPMA110T A
                               LEFT OUTER JOIN BA030T C
                                            ON A.ITEMCD = C.ITEMCD
                       WHERE A.GBN = 'NEW'
                         AND C.ITEMCD IS NULL
                      )
            BEGIN
                RAISERROR('발주 상세를 확인해주세요.', 16, 1);
                RETURN;
            END

            IF @WORKTYPE = 'NEW'
            BEGIN
                EXEC SP_SYSTEM_BA100T_KEYCODE @ORGDIV, 'MA100T', @PURDT, @NEWSEQ OUTPUT
                SET @PURNUM = @PURDT + '-' + CONVERT(VARCHAR(10), @NEWSEQ)

                INSERT INTO MA100T
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
                FROM @TMPMA100T A
            END
            ELSE IF @WORKTYPE = 'EDIT'
            BEGIN
                IF EXISTS (
                           SELECT 1
                           FROM @TMPMA110T A
                                   LEFT OUTER JOIN MA110T B
                                                ON B.ORGDIV = @ORGDIV
                                                AND B.PURNUM = @PURNUM
                                                AND A.PURSEQ2 = B.PURSEQ2
                                   LEFT OUTER JOIN MA110T B1
                                                ON B1.ORGDIV = @ORGDIV
                                                AND B1.PURNUM = @PURNUM
                                                AND A.PURSEQ2 = B1.PURSEQ2
                                                AND A.PLNNUM = B1.PLNNUM
                                                AND A.PLNSEQ = B1.PLNSEQ
                                                AND A.PROCCD = B1.PROCCD
                                                AND A.LOTNUM = B1.LOTNUM
                                                AND A.ITEMCD = B1.ITEMCD
                           WHERE (A.GBN = 'DEL' AND B.PURSEQ2 IS NULL)
                              OR (A.GBN = 'MOD' AND B1.PURSEQ2 IS NULL)
                          )
                   OR EXISTS (
                              SELECT 1
                              FROM @TMPMA110T A
                              WHERE A.GBN IN ('MOD', 'DEL')
                              GROUP BY A.PURSEQ2
                              HAVING COUNT(*) > 1
                             )
                BEGIN
                    RAISERROR('발주 상세의 계획, 단조 LOT 및 수량을 확인해주세요.', 16, 1);
                    RETURN;
                END

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
                FROM MA100T A
                        INNER JOIN @TMPMA100T B
                                ON A.PURNUM = B.PURNUM
                WHERE A.ORGDIV = @ORGDIV

                DELETE A
                FROM SA210T A
                        INNER JOIN @TMPMA110T B
                                ON A.PURSEQ2 = B.PURSEQ2
                                AND B.GBN IN ('MOD', 'DEL')
                WHERE A.ORGDIV = @ORGDIV
                  AND A.PURNUM = @PURNUM
                  AND A.PROCPGMID = 'MA100500'

                DELETE A
                FROM MA110T A
                        INNER JOIN @TMPMA110T B
                                ON A.PURSEQ2 = B.PURSEQ2
                WHERE A.ORGDIV = @ORGDIV
                  AND A.PURNUM = @PURNUM
                  AND B.GBN = 'DEL'

                UPDATE A
                SET A.PURDT     = B.PURDT
                  , A.CUSTCD    = B.CUSTCD
                  , A.AMTUNIT   = B.AMTUNIT
                  , A.WONCHGRAT = B.WONCHGRAT
                FROM MA110T A
                        INNER JOIN @TMPMA100T B
                                ON A.PURNUM = B.PURNUM
                WHERE A.ORGDIV = @ORGDIV

                UPDATE A
                SET A.OUTDT    = B.PURDT
                  , A.OUTYRMM  = LEFT(B.PURDT, 6)
                  , A.CUSTCD   = B.CUSTCD
                  , A.MODDT    = GETDATE()
                  , A.MODEMPNO = @USERID
                  , A.MODIP    = @USERIP
                FROM SA210T A
                        INNER JOIN @TMPMA100T B
                                ON A.PURNUM = B.PURNUM
                WHERE A.ORGDIV = @ORGDIV
                  AND A.PROCPGMID = 'MA100500'

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
                FROM MA110T A
                        INNER JOIN @TMPMA110T B
                                ON A.PURSEQ2 = B.PURSEQ2
                                AND A.PLNNUM = B.PLNNUM
                                AND A.PLNSEQ = B.PLNSEQ
                                AND A.PROCCD = B.PROCCD
                                AND A.LOTNUM = B.LOTNUM
                                AND A.ITEMCD = B.ITEMCD
                WHERE A.ORGDIV = @ORGDIV
                  AND A.PURNUM = @PURNUM
                  AND B.GBN = 'MOD'
            END

            INSERT INTO MA110T
            (
                   ORGDIV   , PURNUM       , PURSEQ2                                                    , PURDIV
                 , PURSTS   , PURDT        , DLVDT                                                      , CUSTCD
                 , ITEMCD   , ITEMNM       , ITEMACNT                                                   , BNATUR
                 , QTY      , QTYUNIT      , UNP                                                        , AMT
                 , WONAMT   , TAXAMT       , AMTUNIT                                                    , WONCHGRAT
                 , TAXDIV   , UNPCALMETH   , PLNNUM
                 , PLNSEQ   , PROCCD       , LOTNUM                                                     , TOTWGT
                 , REMARK   , REGDT        , REGEMPNO                                                   , UNITKG
                 , REGIP    , UNITWGT      , WGTUNIT                                                    , TOTWGTKG
            )
            SELECT @ORGDIV  , @PURNUM      , ISNULL(A1.PURSEQ2, 0) + ROW_NUMBER() OVER (ORDER BY A.SEQ) , '2'
                 , A.PURSTS , B.PURDT      , A.DLVDT                                                    , B.CUSTCD
                 , A.ITEMCD , C.ITEMNM     , C.ITEMACNT                                                 , C.BNATUR
                 , A.QTY    , A.QTYUNIT    , A.UNP                                                      , A.AMT
                 , A.WONAMT , A.TAXAMT     , B.AMTUNIT                                                  , B.WONCHGRAT
                 , 'A'      , A.UNPCALMETH , A.PLNNUM
                 , A.PLNSEQ , A.PROCCD     , A.LOTNUM                                                   , A.QTY * A.UNITWGT
                 , A.REMARK , GETDATE()    , @USERID                                                    , A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
                 , @USERIP  , A.UNITWGT    , A.WGTUNIT                                                  , A.QTY * A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
            FROM @TMPMA110T A
                    CROSS JOIN @TMPMA100T B
                    INNER JOIN BA030T C
                            ON A.ITEMCD = C.ITEMCD
                    LEFT OUTER JOIN (
                                     SELECT T.ORGDIV
                                          , T.PURNUM
                                          , MAX(T.PURSEQ2) AS PURSEQ2
                                     FROM MA110T T
                                     WHERE T.ORGDIV = @ORGDIV
                                       AND T.PURNUM = @PURNUM
                                     GROUP BY T.ORGDIV, T.PURNUM
                                    ) A1
                                    ON A1.ORGDIV = @ORGDIV
                                    AND A1.PURNUM = @PURNUM
            WHERE A.GBN = 'NEW'

            IF NOT EXISTS (
                           SELECT 1
                           FROM MA110T A
                           WHERE A.ORGDIV = @ORGDIV
                             AND A.PURNUM = @PURNUM
                          )
            BEGIN
                RAISERROR('발주 상세를 확인해주세요.', 16, 1);
                RETURN;
            END

            IF EXISTS (
                       SELECT 1
                       FROM @TMPMA110T A
                       WHERE A.GBN IN ('NEW', 'MOD')
                      )
            BEGIN
                EXEC SP_SYSTEM_BA100T_KEYCODE @ORGDIV, 'BA100T', @PURDT, @OUTSEQ OUTPUT

                INSERT INTO SA210T
                (
                       ORGDIV      , RECDT      , SEQ1         , SEQ2
                     , LOCATION    , CUSTCD     , OUTDT        , OUTYRMM
                     , OUTKIND     , OUTTYPE    , ITEMCD       , ITEMNM
                     , ITEMACNT    , BNATUR     , INSIZ        , QTY
                     , QTYUNIT     , UNITWGT    , UNITKG       , TOTWGT
                     , WGTUNIT     , LOTNUM     , ITEMGRADE    , MNGITEM1
                     , OUTDPTCHK   , INRECDT    , INSEQ1       , INSEQ2
                     , PLNNUM      , PLNSEQ     , PURNUM       , PURSEQ2
                     , PROCPGMID   , REGDT      , REGEMPNO     , REGIP
                )
                SELECT @ORGDIV     , @PURDT     , @OUTSEQ      , ROW_NUMBER() OVER (ORDER BY A.PURSEQ2, B.RECDT, B.SEQ1, B.SEQ2)
                     , B1.LOCATION , D.CUSTCD   , @PURDT       , LEFT(@PURDT, 6)
                     , 'F'         , 'A'        , B1.ITEMCD    , B1.ITEMNM
                     , B1.ITEMACNT , B1.BNATUR  , B1.INSIZ     , C.QTY
                     , 'EA'        , B1.UNITWGT , B1.UNITKG    , C.QTY * ISNULL(B1.TOTWGT / NULLIF(B1.QTY, 0), 0)
                     , B1.WGTUNIT  , A.LOTNUM   , B1.ITEMGRADE , B1.MNGITEM1
                     , 'B'         , B.RECDT    , B.SEQ1       , B.SEQ2
                     , A.PLNNUM    , A.PLNSEQ   , @PURNUM      , A.PURSEQ2
                     , 'MA100500'  , GETDATE()  , @USERID      , @USERIP
                FROM (
                      SELECT T.PURSEQ2
                           , T.PLNNUM
                           , T.PLNSEQ
                           , T.LOTNUM
                           , T3.PREVITEMCD
                           , T3.PREVPROCCD
                           , ISNULL(SUM(T.QTY) OVER (PARTITION BY T3.PREVITEMCD, T3.PREVPROCCD, T.LOTNUM
                                                     ORDER BY T.PURSEQ2
                                                     ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS STARTQTY
                           , SUM(T.QTY) OVER (PARTITION BY T3.PREVITEMCD, T3.PREVPROCCD, T.LOTNUM
                                              ORDER BY T.PURSEQ2
                                              ROWS UNBOUNDED PRECEDING) AS ENDQTY
                      FROM MA110T T
                              INNER JOIN (
                                          SELECT T.PLNNUM, T.PLNSEQ, T.PROCCD, T.ITEMCD, T.LOTNUM
                                          FROM @TMPMA110T T
                                          WHERE T.GBN IN ('NEW', 'MOD')
                                          GROUP BY T.PLNNUM, T.PLNSEQ, T.PROCCD, T.ITEMCD, T.LOTNUM
                                         ) T1
                                         ON T.PLNNUM = T1.PLNNUM
                                         AND T.PLNSEQ = T1.PLNSEQ
                                         AND T.PROCCD = T1.PROCCD
                                         AND T.ITEMCD = T1.ITEMCD
                                         AND T.LOTNUM = T1.LOTNUM
                              LEFT OUTER JOIN (
                                               SELECT T.PURSEQ2
                                               FROM SA210T T
                                               WHERE T.ORGDIV = @ORGDIV
                                                 AND T.PURNUM = @PURNUM
                                                 AND T.PROCPGMID = 'MA100500'
                                               GROUP BY T.PURSEQ2
                                              ) T2
                                              ON T.PURSEQ2 = T2.PURSEQ2
                              INNER JOIN (
                                          SELECT T.ORDNUM AS PLNNUM
                                               , T.ORGDIV
                                               , T.ORDSEQ AS PLNSEQ
                                               , T.SDATE AS PLANDT
                                               , T.PROCCD
                                               , T.ITEMCD
                                               , T2.PREVITEMCD
                                               , T2.PREVPROCCD
                                          FROM PR110T T
                                                  INNER JOIN SA110T T1
                                                          ON T.ORGDIV = T1.ORGDIV
                                                          AND T.SAORDNUM = T1.ORDNUM
                                                          AND T.SAORDSEQ = T1.ORDSEQ
                                                  INNER JOIN (
                                                              SELECT T.PRNTITEMCD, T.CHLDITEMCD, T.PROCCD
                                                                   , LAG(T.CHLDITEMCD) OVER (PARTITION BY T.PRNTITEMCD ORDER BY T.SORT, T.PROCCD, T.CHLDITEMCD) AS PREVITEMCD
                                                                   , LAG(T.PROCCD) OVER (PARTITION BY T.PRNTITEMCD ORDER BY T.SORT, T.PROCCD, T.CHLDITEMCD) AS PREVPROCCD
                                                              FROM BA031T T
                                                              WHERE T.USEYN = 'Y' OR T.USEYN IS NULL
                                                             ) T2
                                                             ON T1.ITEMCD = T2.PRNTITEMCD
                                                             AND T.ITEMCD = T2.CHLDITEMCD
                                                             AND T.PROCCD = T2.PROCCD
                                                  INNER JOIN BA011T T3
                                                          ON T3.MAINCD = 'BA030'
                                                          AND T.PROCCD = T3.SUBCD
                                                          AND T3.USEYN = 'Y'
                                                          AND T3.CHRREF1 = 'Y'
                                          WHERE T.ORGDIV = @ORGDIV
                                         ) T3
                                         ON T.PLNNUM = T3.PLNNUM
                                         AND T.PLNSEQ = T3.PLNSEQ
                                         AND T.PROCCD = T3.PROCCD
                                         AND T.ITEMCD = T3.ITEMCD
                              INNER JOIN (
                                          SELECT DISTINCT T.ORGDIV, T.PROCCD, T.ITEMCD
                                               , (CASE WHEN T.PROCCD <> '00' THEN T.ORDNUM END) AS ORDNUM
                                               , (CASE WHEN T.PROCCD <> '00' THEN T.ORDSEQ END) AS ORDSEQ
                                          FROM PR110T T
                                                  LEFT OUTER JOIN (
                                                                   SELECT T.ORGDIV, T.ORDNUM, T.ORDSEQ, T.PROCCD
                                                                        , SUM(T1.QTY) AS QTY
                                                                   FROM PR210T T
                                                                           CROSS APPLY (
                                                                                        SELECT T.PRODQTY AS QTY

                                                                                        UNION ALL

                                                                                        SELECT T1.BADQTY
                                                                                        FROM PR212T T1
                                                                                        WHERE T1.ORGDIV = T.ORGDIV
                                                                                          AND T1.PRODNUM = T.RECDT + '-' + CONVERT(VARCHAR(10), T.SEQ1)
                                                                                          AND T1.PRODSEQ = T.SEQ2
                                                                                       ) T1
                                                                   WHERE T.ORGDIV = @ORGDIV
                                                                   GROUP BY T.ORGDIV, T.ORDNUM
                                                                          , T.ORDSEQ, T.PROCCD
                                                                  ) T1
                                                                  ON T.ORGDIV = T1.ORGDIV
                                                                  AND T.ORDNUM = T1.ORDNUM
                                                                  AND T.ORDSEQ = T1.ORDSEQ
                                                                  AND T.PROCCD = T1.PROCCD
                                          WHERE T.ORGDIV = @ORGDIV
                                            AND (T.FINYN = 'Y' OR ISNULL(T1.QTY, 0) >= T.QTY)
                                         ) T4
                                         ON T3.ORGDIV = T4.ORGDIV
                                         AND T3.PREVPROCCD = T4.PROCCD
                                         AND T3.PREVITEMCD = T4.ITEMCD
                                         AND (T4.PROCCD = '00' OR (T3.PLNNUM = T4.ORDNUM AND T3.PLNSEQ = T4.ORDSEQ))
                      WHERE T.ORGDIV = @ORGDIV
                        AND T.PURNUM = @PURNUM
                        AND T2.PURSEQ2 IS NULL
                     ) A
                        INNER JOIN (
                                    SELECT T.RECDT, T.SEQ1, T.SEQ2
                                         , T.ITEMCD, T.PROCCD, T.ORGLOTNUM
                                         , ISNULL(SUM(T.QTY) OVER (PARTITION BY T.ITEMCD, T.PROCCD, T.ORGLOTNUM
                                                                   ORDER BY T.INDT, T.RECDT, T.SEQ1, T.SEQ2
                                                                   ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS STARTQTY
                                         , SUM(T.QTY) OVER (PARTITION BY T.ITEMCD, T.PROCCD, T.ORGLOTNUM
                                                            ORDER BY T.INDT, T.RECDT, T.SEQ1, T.SEQ2
                                                            ROWS UNBOUNDED PRECEDING) AS ENDQTY
                                    FROM (
                                          SELECT T.RECDT, T.SEQ1, T.SEQ2, T.INDT
                                               , T.ITEMCD, T.PROCCD, T.ORGLOTNUM
                                               , T1.QTY
                                          FROM MA210T T
                                                  INNER JOIN (
                                                              SELECT T.LOTNUM
                                                              FROM @TMPMA110T T
                                                              WHERE T.GBN IN ('NEW', 'MOD')
                                                              GROUP BY T.LOTNUM
                                                             ) T3
                                                             ON T.ORGLOTNUM = T3.LOTNUM
                                                  CROSS APPLY (
                                                               SELECT SUM(T2.QTY) AS QTY
                                                               FROM (
                                                                     SELECT T.QTY

                                                                     UNION ALL

                                                                     SELECT -T1.QTY
                                                                     FROM SA210T T1
                                                                     WHERE T1.ORGDIV = T.ORGDIV
                                                                       AND T1.INRECDT = T.RECDT
                                                                       AND T1.INSEQ1 = T.SEQ1
                                                                       AND T1.INSEQ2 = T.SEQ2
                                                                    ) T2
                                                              ) T1
                                          WHERE T.ORGDIV = @ORGDIV
                                            AND ISNULL(T.QTYUNIT, '') IN ('', 'EA')
                                            AND T.QTY IS NOT NULL
                                            AND T1.QTY > 0
                                         ) T
                                   ) B
                                   ON A.PREVITEMCD = B.ITEMCD
                                   AND A.PREVPROCCD = B.PROCCD
                                   AND A.LOTNUM = B.ORGLOTNUM
                        INNER JOIN MA210T B1
                                ON B1.ORGDIV = @ORGDIV
                                AND B.RECDT = B1.RECDT
                                AND B.SEQ1 = B1.SEQ1
                                AND B.SEQ2 = B1.SEQ2
                        CROSS APPLY (
                                     SELECT SUM(T.QTY) AS QTY
                                     FROM (VALUES ((CASE WHEN A.ENDQTY < B.ENDQTY THEN A.ENDQTY ELSE B.ENDQTY END)),
                                                  (-(CASE WHEN A.STARTQTY > B.STARTQTY THEN A.STARTQTY ELSE B.STARTQTY END))) T(QTY)
                                    ) C
                        CROSS JOIN @TMPMA100T D
                WHERE C.QTY > 0

                IF EXISTS (
                           SELECT 1
                           FROM MA110T A
                                   INNER JOIN (
                                               SELECT T.PLNNUM, T.PLNSEQ, T.PROCCD, T.ITEMCD, T.LOTNUM
                                               FROM @TMPMA110T T
                                               WHERE T.GBN IN ('NEW', 'MOD')
                                               GROUP BY T.PLNNUM, T.PLNSEQ, T.PROCCD, T.ITEMCD
                                                      , T.LOTNUM
                                              ) A1
                                              ON A.PLNNUM = A1.PLNNUM
                                              AND A.PLNSEQ = A1.PLNSEQ
                                              AND A.PROCCD = A1.PROCCD
                                              AND A.ITEMCD = A1.ITEMCD
                                              AND A.LOTNUM = A1.LOTNUM
                                   LEFT OUTER JOIN (
                                                    SELECT T.PURSEQ2
                                                         , SUM(T.QTY) AS QTY
                                                    FROM SA210T T
                                                    WHERE T.ORGDIV = @ORGDIV
                                                      AND T.PURNUM = @PURNUM
                                                      AND T.PROCPGMID = 'MA100500'
                                                    GROUP BY T.PURSEQ2
                                                   ) B
                                                   ON A.PURSEQ2 = B.PURSEQ2
                           WHERE A.ORGDIV = @ORGDIV
                             AND A.PURNUM = @PURNUM
                             AND A.QTY <> ISNULL(B.QTY, 0)
                          )
                BEGIN
                    RAISERROR('외주발주 수량이 직전공정의 단조 LOT 재고 잔량을 초과합니다.', 16, 1);
                    RETURN;
                END
            END

            SET @OUTPUT = @PURNUM
        END

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
