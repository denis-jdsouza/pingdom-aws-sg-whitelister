pipeline {

    agent any

    parameters {
        choice(
            name: 'DRY_RUN', 
            choices: ['false', 'true'], 
            description: 'If "true" automation will NOT make changes to AWS Security group & NOT send Slack alerts.'
        )
    }

    triggers {
        cron('H */12 * * *') // Runs every 12 hours (update based on requirements)
    }

    environment {
        SLACK_BOT_TOKEN = credentials('<SLACK_TOKEN>') // update value
        PINGDOM_API_TOKEN = credentials('<PINGDOM_API_TOKEN>') // update value
        PINGDOM_REGION = "NA" // North America
        AWS_SG_ID = "<AWS_security_group_ID>" // update value
        AWS_REGION = "<AWS_region>"           // update value
        
        DRY_RUN = params.DRY_RUN
        JENKINS_URL = env.JENKINS_URL
        JOB_NAME = env.JOB_NAME
    }

    options {
        disableConcurrentBuilds()
        ansiColor('xterm')
    }

    stages {
        stage('Docker Build') {
            steps {
                sh 'docker build --network=host -t pingdom-aws-sg-whitelister .'
            }
        }

        stage('Generate .env file') {
            steps {
                sh '''
                    cat <<EOF > params_${BUILD_NUMBER}.env
                    DRY_RUN=${DRY_RUN}
                    SLACK_BOT_TOKEN=${SLACK_BOT_TOKEN}
                    PINGDOM_API_TOKEN=${PINGDOM_API_TOKEN}
                    PINGDOM_REGION=${PINGDOM_REGION}
                    JENKINS_URL=${JENKINS_URL}
                    JOB_NAME=${JOB_NAME}
                    AWS_REGION=${AWS_REGION}
                    AWS_SG_ID=${AWS_SG_ID}
                    EOF
                '''
            }
        }

        stage('Docker Run and Sync') {
            steps {
                sh "docker run --name pingdom-aws-sg-whitelister-${BUILD_NUMBER} --env-file=params_${BUILD_NUMBER}.env --rm pingdom-aws-sg-whitelister"
            }
        }
    }

    post {
        always {
            sh "rm -f params_${BUILD_NUMBER}.env"
        }
    }
}