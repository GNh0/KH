USE [PROJECT_A]
GO
/****** Object:  StoredProcedure [dbo].[sp_XM100500_SAVE]    Script Date: 2026-11-19 오후 1:54:06 ******/
SET ANSI_NULLS ON
GO
SET QUOTED_IDENTIFIER ON
GO
-- =============================================
-- AUTHOR:      사용자
-- CREATE DATE: 2026.11.19
-- DESCRIPTION: 외주발주 처리
-- =============================================
ALTER PROCEDURE [dbo].[sp_XM100500_SAVE]
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
          , @LASTSEQ        INT
          , @OUTSEQ         INT
          , @NEWCOUNT       INT
          , @MODCOUNT       INT
          , @DELCOUNT       INT

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

    DECLARE @TMPISSUE TABLE
    (
          PURSEQ2 INT             , RECDT VARCHAR(50)      , SEQ1 INT
        , SEQ2 INT                 , QTY NUMERIC(18, 4)
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

        IF @STARTTRANCOUNT = 0
        BEGIN
            BEGIN TRANSACTION
        END

        IF @WORKTYPE IN ('EDIT', 'DELETE')
        BEGIN
            IF NOT EXISTS (
                           SELECT 1
                           FROM @TMPXX100T
                          )
               OR EXISTS (
                          SELECT 1
                          FROM @TMPXX100T A
                                  LEFT OUTER JOIN XX100T B WITH (UPDLOCK, HOLDLOCK)
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
                       FROM @TMPXX100T A
                               INNER JOIN XM210T B WITH (UPDLOCK, HOLDLOCK)
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

            IF @STARTTRANCOUNT = 0
            BEGIN
                COMMIT TRANSACTION
            END
            RETURN;
        END

        IF (SELECT COUNT(*) FROM @TMPXX100T) <> 1
           OR EXISTS (
                      SELECT 1
                      FROM @TMPXX100T A
                      WHERE ISNULL(A.CUSTCD, '') = ''
                         OR TRY_CONVERT(DATE, NULLIF(A.PURDT, ''), 112) IS NULL
                     )
        BEGIN
            RAISERROR('발주일자와 외주업체를 확인해주세요.', 16, 1);
            RETURN;
        END

        SELECT @PURNUM = A.PURNUM
             , @PURDT = A.PURDT
        FROM @TMPXX100T A

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

        IF EXISTS (
                   SELECT 1
                   FROM @TMPXX110T A
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
        END

        SELECT @NEWCOUNT = COUNT(CASE WHEN A.GBN = 'NEW' THEN 1 END)
             , @MODCOUNT = COUNT(CASE WHEN A.GBN = 'MOD' THEN 1 END)
             , @DELCOUNT = COUNT(CASE WHEN A.GBN = 'DEL' THEN 1 END)
        FROM @TMPXX110T A

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
                INNER JOIN (
                            SELECT DISTINCT T.ORGDIV, T.PROCCD, T.ITEMCD
                                 , (CASE WHEN T.PROCCD <> '00' THEN T.ORDNUM END) AS ORDNUM
                                 , (CASE WHEN T.PROCCD <> '00' THEN T.ORDSEQ END) AS ORDSEQ
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
                              AND (T.FINYN = 'Y' OR ISNULL(T1.QTY, 0) >= T.QTY)
                           ) B1
                           ON B.ORGDIV = B1.ORGDIV
                           AND B.PREVPROCCD = B1.PROCCD
                           AND B.PREVITEMCD = B1.ITEMCD
                           AND (B1.PROCCD = '00' OR (B.PLNNUM = B1.ORDNUM AND B.PLNSEQ = B1.ORDSEQ))
        WHERE A.GBN IN ('NEW', 'MOD')

        IF EXISTS (
                   SELECT 1
                   FROM @TMPXX110T A
                   WHERE A.GBN IN ('NEW', 'MOD')
                     AND A.PREVITEMCD IS NULL
                  )
        BEGIN
            RAISERROR('직전공정이 완료된 외주 작업지시를 선택해주세요.', 16, 1);
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

            IF @@ROWCOUNT <> @DELCOUNT
            BEGIN
                RAISERROR('발주 상세의 계획, 단조 LOT 및 수량을 확인해주세요.', 16, 1);
            END

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

            IF @@ROWCOUNT <> @MODCOUNT
            BEGIN
                RAISERROR('발주 상세의 계획, 단조 LOT 및 수량을 확인해주세요.', 16, 1);
            END
        END

        SELECT @LASTSEQ = ISNULL(MAX(A.PURSEQ2), 0)
        FROM XX110T A
        WHERE A.ORGDIV = @ORGDIV
          AND A.PURNUM = @PURNUM

        UPDATE A
        SET A.PURSEQ2 = @LASTSEQ + B.RN
        FROM @TMPXX110T A
                INNER JOIN (
                            SELECT T.SEQ
                                 , ROW_NUMBER() OVER (ORDER BY T.SEQ) AS RN
                            FROM @TMPXX110T T
                            WHERE T.GBN = 'NEW'
                           ) B
                           ON A.SEQ = B.SEQ

        INSERT INTO XX110T
        (
               ORGDIV   , PURNUM       , PURSEQ2    , PURDIV
             , PURSTS   , PURDT        , DLVDT      , CUSTCD
             , ITEMCD   , ITEMNM       , ITEMACNT   , BNATUR
             , QTY      , QTYUNIT      , UNP        , AMT
             , WONAMT   , TAXAMT       , AMTUNIT    , WONCHGRAT
             , TAXDIV   , UNPCALMETH   , PLNNUM
             , PLNSEQ   , PROCCD       , LOTNUM     , TOTWGT
             , REMARK   , REGDT        , REGEMPNO   , UNITKG
             , REGIP    , UNITWGT      , WGTUNIT    , TOTWGTKG
        )
        SELECT @ORGDIV  , @PURNUM      , A.PURSEQ2  , '2'
             , A.PURSTS , B.PURDT      , A.DLVDT    , B.CUSTCD
             , A.ITEMCD , C.ITEMNM     , C.ITEMACNT , C.BNATUR
             , A.QTY    , A.QTYUNIT    , A.UNP      , A.AMT
             , A.WONAMT , A.TAXAMT     , B.AMTUNIT  , B.WONCHGRAT
             , 'A'      , A.UNPCALMETH , A.PLNNUM
             , A.PLNSEQ , A.PROCCD     , A.LOTNUM   , A.QTY * A.UNITWGT
             , A.REMARK , GETDATE()    , @USERID    , A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
             , @USERIP  , A.UNITWGT    , A.WGTUNIT  , A.QTY * A.UNITWGT * (CASE WHEN A.WGTUNIT = 'G' THEN 0.001 ELSE 1 END)
        FROM @TMPXX110T A
                CROSS JOIN @TMPXX100T B
                INNER JOIN MS030T C
                        ON A.ITEMCD = C.ITEMCD
        WHERE A.GBN = 'NEW'

        IF @@ROWCOUNT <> @NEWCOUNT
        BEGIN
            RAISERROR('발주 상세를 확인해주세요.', 16, 1);
        END

        IF NOT EXISTS (
                       SELECT 1
                       FROM XX110T A
                       WHERE A.ORGDIV = @ORGDIV
                         AND A.PURNUM = @PURNUM
                      )
        BEGIN
            RAISERROR('발주 상세를 확인해주세요.', 16, 1);
        END

        INSERT INTO @TMPISSUE (PURSEQ2, RECDT, SEQ1, SEQ2, QTY)
        SELECT A.PURSEQ2, B.RECDT, B.SEQ1, B.SEQ2, C.QTY
        FROM (
              SELECT T.PURSEQ2
                   , T.PREVITEMCD
                   , T.PREVPROCCD
                   , T.LOTNUM
                   , ISNULL(SUM(T.QTY) OVER (PARTITION BY T.PREVITEMCD, T.PREVPROCCD, T.LOTNUM
                                             ORDER BY T.PURSEQ2
                                             ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING), 0) AS STARTQTY
                   , SUM(T.QTY) OVER (PARTITION BY T.PREVITEMCD, T.PREVPROCCD, T.LOTNUM
                                      ORDER BY T.PURSEQ2
                                      ROWS UNBOUNDED PRECEDING) AS ENDQTY
              FROM @TMPXX110T T
              WHERE T.GBN IN ('NEW', 'MOD')
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
                                  FROM XM210T T WITH (UPDLOCK, HOLDLOCK)
                                          INNER JOIN (
                                                      SELECT DISTINCT T.PREVITEMCD, T.PREVPROCCD, T.LOTNUM
                                                      FROM @TMPXX110T T
                                                      WHERE T.GBN IN ('NEW', 'MOD')
                                                     ) T3
                                                     ON T.ITEMCD = T3.PREVITEMCD
                                                     AND T.PROCCD = T3.PREVPROCCD
                                                     AND T.ORGLOTNUM = T3.LOTNUM
                                          CROSS APPLY (
                                                       SELECT SUM(T2.QTY) AS QTY
                                                       FROM (
                                                             SELECT T.QTY

                                                             UNION ALL

                                                             SELECT -T1.QTY
                                                             FROM XS210T T1 WITH (UPDLOCK, HOLDLOCK)
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
                CROSS APPLY (
                             SELECT SUM(T.QTY) AS QTY
                             FROM (VALUES ((CASE WHEN A.ENDQTY < B.ENDQTY THEN A.ENDQTY ELSE B.ENDQTY END)),
                                          (-(CASE WHEN A.STARTQTY > B.STARTQTY THEN A.STARTQTY ELSE B.STARTQTY END))) T(QTY)
                            ) C
        WHERE C.QTY > 0

        IF EXISTS (
                   SELECT 1
                   FROM @TMPXX110T A
                           LEFT OUTER JOIN (
                                            SELECT T.PURSEQ2
                                                 , SUM(T.QTY) AS QTY
                                            FROM @TMPISSUE T
                                            GROUP BY T.PURSEQ2
                                           ) B
                                           ON A.PURSEQ2 = B.PURSEQ2
                   WHERE A.GBN IN ('NEW', 'MOD')
                     AND A.QTY <> ISNULL(B.QTY, 0)
                  )
        BEGIN
            RAISERROR('외주발주 수량이 직전공정의 단조 LOT 재고 잔량을 초과합니다.', 16, 1);
            RETURN;
        END

        IF EXISTS (
                   SELECT 1
                   FROM @TMPISSUE
                  )
        BEGIN
            EXEC SP_NEW_KEY @ORGDIV, 'SY100T', @PURDT, @OUTSEQ OUTPUT

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
            SELECT @ORGDIV    , @PURDT    , @OUTSEQ     , ROW_NUMBER() OVER (ORDER BY A.PURSEQ2, A.RECDT, A.SEQ1, A.SEQ2)
                 , B.LOCATION , D.CUSTCD  , @PURDT      , LEFT(@PURDT, 6)
                 , 'F'        , 'A'       , B.ITEMCD    , B.ITEMNM
                 , B.ITEMACNT , B.BNATUR  , B.INSIZ     , A.QTY
                 , 'EA'       , B.UNITWGT , B.UNITKG    , A.QTY * ISNULL(B.TOTWGT / NULLIF(B.QTY, 0), 0)
                 , B.WGTUNIT  , C.LOTNUM  , B.ITEMGRADE , B.MNGITEM1
                 , 'B'        , A.RECDT   , A.SEQ1      , A.SEQ2
                 , C.PLNNUM   , C.PLNSEQ  , @PURNUM     , A.PURSEQ2
                 , 'XM100500' , GETDATE() , @USERID     , @USERIP
            FROM @TMPISSUE A
                    INNER JOIN XM210T B
                            ON B.ORGDIV = @ORGDIV
                            AND A.RECDT = B.RECDT
                            AND A.SEQ1 = B.SEQ1
                            AND A.SEQ2 = B.SEQ2
                    INNER JOIN @TMPXX110T C
                            ON A.PURSEQ2 = C.PURSEQ2
                            AND C.GBN IN ('NEW', 'MOD')
                    CROSS JOIN @TMPXX100T D
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
